from __future__ import annotations

import ipaddress
import datetime
import enum
import re
import json
from typing import Optional, List, Set

from sqlalchemy import Column, Integer, Unicode, String, UniqueConstraint
from sqlalchemy import Enum, DateTime, Boolean
from sqlalchemy import ForeignKey
from sqlalchemy import event
from sqlalchemy.orm import relationship
from sqlalchemy_utils import IPAddressType

import cnaas_nms.db.base
import cnaas_nms.db.site
import cnaas_nms.db.linknet

from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.db.stackmember import Stackmember
from cnaas_nms.tools.event import add_event


class DeviceException(Exception):
    pass


class DeviceStateException(DeviceException):
    pass


class DeviceState(enum.Enum):
    UNKNOWN = 0         # Unhandled programming error
    PRE_CONFIGURED = 1  # Pre-populated, not seen yet
    DHCP_BOOT = 2       # Something booted via DHCP, unknown device
    DISCOVERED = 3      # Something booted with base config, temp ssh access for conf push
    INIT = 4            # Moving to management VLAN, applying base template
    MANAGED = 5         # Correct managament and accessible via conf push
    MANAGED_NOIF = 6    # Only base system template managed, no interfaces?
    UNMANAGED = 99      # Device no longer maintained by conf push

    @classmethod
    def has_value(cls, value):
        return any(value == item.value for item in cls)

    @classmethod
    def has_name(cls, value):
        return any(value == item.name for item in cls)


class DeviceType(enum.Enum):
    UNKNOWN = 0
    ACCESS = 1
    DIST = 2
    CORE = 3

    @classmethod
    def has_value(cls, value):
        return any(value == item.value for item in cls)

    @classmethod
    def has_name(cls, value):
        return any(value == item.name for item in cls)


class Device(cnaas_nms.db.base.Base):
    __tablename__ = 'device'
    __table_args__ = (
        None,
        UniqueConstraint('hostname'),
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    hostname = Column(String(64), nullable=False)
    site_id = Column(Integer, ForeignKey('site.id'))
    site = relationship("Site")
    description = Column(Unicode(255))
    management_ip = Column(IPAddressType)
    dhcp_ip = Column(IPAddressType)
    infra_ip = Column(IPAddressType)
    oob_ip = Column(IPAddressType)
    serial = Column(String(64))
    ztp_mac = Column(String(12))
    platform = Column(String(64))
    vendor = Column(String(64))
    model = Column(String(64))
    os_version = Column(String(64))
    synchronized = Column(Boolean, default=False)
    state = Column(Enum(DeviceState), nullable=False)  # type: ignore
    device_type = Column(Enum(DeviceType), nullable=False)
    confhash = Column(String(64))  # SHA256 = 64 characters
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)  # onupdate=now
    port = Column(Integer)
    is_stack = Column(Boolean, default=False)

    def as_dict(self) -> dict:
        """Return JSON serializable dict."""
        d = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if issubclass(value.__class__, enum.Enum):
                value = value.name
            elif issubclass(value.__class__, cnaas_nms.db.base.Base):
                continue
            elif issubclass(value.__class__, ipaddress.IPv4Address):
                value = str(value)
            elif issubclass(value.__class__, datetime.datetime):
                value = str(value)
            d[col.name] = value
        return d

    def get_neighbors(self, session) -> List[Device]:
        """Look up neighbors from cnaas_nms.db.linknet.Linknets and return them as a list of Device objects."""
        linknets = self.get_linknets(session)
        ret = []
        for linknet in linknets:
            if linknet.device_a_id == self.id:
                ret.append(session.query(Device).filter(Device.id == linknet.device_b_id).one())
            else:
                ret.append(session.query(Device).filter(Device.id == linknet.device_a_id).one())
        return ret

    def get_linknets(self, session) -> List[cnaas_nms.db.linknet.Linknet]:
        """Look up linknets and return a list of Linknet objects."""
        ret = []
        linknets = session.query(cnaas_nms.db.linknet.Linknet).\
            filter(
                (cnaas_nms.db.linknet.Linknet.device_a_id == self.id)
                |
                (cnaas_nms.db.linknet.Linknet.device_b_id == self.id)
            )
        for linknet in linknets:
            ret.append(linknet)
        return ret

    def get_linknet_localif_mapping(self, session) -> dict[str, str]:
        """Return a mapping with local interface name and what peer device hostname
        that interface is connected to."""
        linknets: List[cnaas_nms.db.linknet.Linknet] = self.get_linknets(session)
        ret = {}
        for linknet in linknets:
            if linknet.device_a == self:
                ret[linknet.device_a_port] = linknet.device_b.hostname
            elif linknet.device_b == self:
                ret[linknet.device_b_port] = linknet.device_a.hostname
            else:
                raise Exception("Got invalid linknets for device {}: {}".format(
                    self.hostname, linknets
                ))
        return ret

    def get_links_to(self, session, peer_device: Device) -> List[cnaas_nms.db.linknet.Linknet]:
        """Return linknet connecting to device peer_device."""
        return session.query(cnaas_nms.db.linknet.Linknet).\
            filter(
                ((cnaas_nms.db.linknet.Linknet.device_a_id == self.id) &
                 (cnaas_nms.db.linknet.Linknet.device_b_id == peer_device.id))
                |
                ((cnaas_nms.db.linknet.Linknet.device_b_id == self.id) &
                 (cnaas_nms.db.linknet.Linknet.device_a_id == peer_device.id))
            ).all()

    def get_neighbor_local_ifname(self, session, peer_device: Device) -> Optional[str]:
        """Get the local interface name on this device that links to peer_device."""
        linknets = self.get_links_to(session, peer_device)
        if not linknets:
            return None
        elif len(linknets) > 1:
            raise ValueError("Multiple linknets between devices not supported")
        else:
            linknet = linknets[0]
        if linknet.device_a_id == self.id:
            return linknet.device_a_port
        elif linknet.device_b_id == self.id:
            return linknet.device_b_port

    def get_neighbor_local_ifnames(self, session, peer_device: Device) -> List[str]:
        """Get the local interface name on this device that links to peer_device."""
        linknets = self.get_links_to(session, peer_device)
        ifnames = []
        if not linknets:
            return ifnames
        for linknet in linknets:
            if linknet.device_a_id == self.id:
                ifnames.append(linknet.device_a_port)
            elif linknet.device_b_id == self.id:
                ifnames.append(linknet.device_b_port)
        return ifnames

    def get_neighbor_local_ipif(self, session, peer_device: Device) -> Optional[str]:
        """Get the local interface IP on this device that links to peer_device."""
        linknets = self.get_links_to(session, peer_device)
        if not linknets:
            return None
        elif len(linknets) > 1:
            raise ValueError("Multiple linknets between devices not supported")
        else:
            linknet = linknets[0]
        if linknet.device_a_id == self.id:
            return "{}/{}".format(linknet.device_a_ip, ipaddress.IPv4Network(linknet.ipv4_network).prefixlen)
        elif linknet.device_b_id == self.id:
            return "{}/{}".format(linknet.device_b_ip, ipaddress.IPv4Network(linknet.ipv4_network).prefixlen)

    def get_neighbor_ip(self, session, peer_device: Device):
        """Get the remote peer IP address for the linknet going towards device."""
        linknets = self.get_links_to(session, peer_device)
        if not linknets:
            return None
        elif len(linknets) > 1:
            raise ValueError("Multiple linknets between devices not supported")
        else:
            linknet = linknets[0]
        if linknet.device_a_id == self.id:
            return linknet.device_b_ip
        elif linknet.device_b_id == self.id:
            return linknet.device_a_ip

    def get_uplink_peer_hostnames(self, session) -> List[str]:
        intfs = session.query(Interface).filter(Interface.device == self).\
            filter(Interface.configtype == InterfaceConfigType.ACCESS_UPLINK).all()
        peer_hostnames = []
        intf: Interface = Interface()
        for intf in intfs:
            if intf.data:
                peer_hostnames.append(intf.data['neighbor'])
        return peer_hostnames

    def get_mlag_peer(self, session) -> Optional[Device]:
        intfs = session.query(Interface).filter(Interface.device == self). \
            filter(Interface.configtype == InterfaceConfigType.MLAG_PEER).all()
        peers: Set[Device] = set()
        linknets = self.get_linknets(session)
        intf: Interface = Interface()
        for intf in intfs:
            for linknet in linknets:
                if linknet.device_a == self and linknet.device_a_port == intf.name:
                    peers.add(linknet.device_b)
                elif linknet.device_b == self and linknet.device_b_port == intf.name:
                    peers.add(linknet.device_a)
        if len(peers) > 1:
            raise DeviceException("More than one MLAG peer found: {}".format(
                [x.hostname for x in peers]
            ))
        elif len(peers) == 1:
            peer_devtype = next(iter(peers)).device_type
            if self.device_type == DeviceType.UNKNOWN or peer_devtype == DeviceType.UNKNOWN:
                # Ignore check during INIT, one device might be UNKNOWN
                pass
            elif self.device_type != peer_devtype:
                raise DeviceException("MLAG peers are not the same device type")
            return next(iter(peers))
        else:
            return None

    def get_stackmembers(self, session) -> Optional[Stackmember]:
        """Return all stackmembers belonging to a device (if any)"""
        members = session.query(Stackmember).filter(Stackmember.device == self).all()
        return members

    @classmethod
    def valid_hostname(cls, hostname: str) -> bool:
        if not isinstance(hostname, str):
            return False
        if hostname.endswith('.'):
            hostname = hostname[:-1]
        if len(hostname) < 1 or len(hostname) > 253:
            return False
        hostname_part_re = re.compile('^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$',
                                      re.IGNORECASE)
        return all(hostname_part_re.match(x) for x in hostname.split('.'))

    @classmethod
    def set_devtype_syncstatus(cls, session, devtype: DeviceType,
                               platform: Optional[str] = None, syncstatus=False):
        """Update sync status of devices of type devtype"""
        dev: Device
        if platform:
            dev_query = session.query(Device).filter(Device.device_type == devtype).\
                filter(Device.platform == platform).all()
        else:
            dev_query = session.query(Device).filter(Device.device_type == devtype).all()
        for dev in dev_query:
            dev.synchronized = syncstatus

    @classmethod
    def device_create(cls, **kwargs) -> Device:
        data, errors = cls.validate(**kwargs)
        if errors != []:
            raise ValueError("Validation errors: {}".format(errors))

        new_device = Device()
        for field in data:
            setattr(new_device, field, data[field])
        return new_device

    def device_update(self, **kwargs):
        data, error = self.validate(new_entry=False, **kwargs)
        if error != []:
            return error
        for field in data:
            setattr(self, field, data[field])

    @classmethod
    def set_config_hash(cls, session, hostname, hexdigest):
        instance: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not instance:
            return 'Device not found'
        instance.confhash = hexdigest

    @classmethod
    def get_config_hash(cls, session, hostname):
        instance: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not instance:
            return None
        return instance.confhash

    @classmethod
    def validate(cls, new_entry=True, **kwargs):
        data = {}
        errors = []
        if 'hostname' in kwargs:
            if Device.valid_hostname(kwargs['hostname']):
                data['hostname'] = kwargs['hostname']
            else:
                errors.append("Invalid hostname received")
        else:
            if new_entry:
                errors.append('Required field hostname not found')

        if 'site_id' in kwargs:
            try:
                site_id = int(kwargs['site_id'])
            except Exception:
                errors.append('Invalid site_id recevied, must be an integer.')
            else:
                data['site_id'] = site_id

        if 'description' in kwargs:
            data['description'] = kwargs['description']

        if 'management_ip' in kwargs:
            if kwargs['management_ip']:
                try:
                    addr = ipaddress.IPv4Address(kwargs['management_ip'])
                except Exception:
                    errors.append('Invalid management_ip received. Must be correct IPv4 address.')
                else:
                    data['management_ip'] = addr
            else:
                data['management_ip'] = None

        if 'infra_ip' in kwargs:
            if kwargs['infra_ip']:
                try:
                    addr = ipaddress.IPv4Address(kwargs['infra_ip'])
                except Exception:
                    errors.append('Invalid infra_ip received. Must be correct IPv4 address.')
                else:
                    data['infra_ip'] = addr
            else:
                data['infra_ip'] = None

        if 'dhcp_ip' in kwargs:
            if kwargs['dhcp_ip']:
                try:
                    addr = ipaddress.IPv4Address(kwargs['dhcp_ip'])
                except Exception:
                    errors.append('Invalid dhcp_ip received. Must be correct IPv4 address.')
                else:
                    data['dhcp_ip'] = addr
            else:
                data['dhcp_ip'] = None

        if 'serial' in kwargs:
            try:
                serial = str(kwargs['serial']).upper()
            except Exception:
                errors.append('Invalid device serial received.')
            else:
                data['serial'] = serial

        if 'ztp_mac' in kwargs:
            try:
                ztp_mac = str(kwargs['ztp_mac']).upper()
            except Exception:
                errors.append('Invalid device ztp_mac received.')
            else:
                data['ztp_mac'] = ztp_mac

        if 'platform' in kwargs:
            data['platform'] = kwargs['platform']

        if 'vendor' in kwargs:
            data['vendor'] = kwargs['vendor']

        if 'model' in kwargs:
            data['model'] = kwargs['model']

        if 'os_version' in kwargs:
            data['os_version'] = kwargs['os_version']

        if 'synchronized' in kwargs:
            if isinstance(kwargs['synchronized'], bool):
                data['synchronized'] = kwargs['synchronized']
            else:
                errors.append("Invalid synchronization state received")
        if 'state' in kwargs:
            if isinstance(kwargs['state'], DeviceState):
                data['state'] = kwargs['state']
            else:
                try:
                    state = str(kwargs['state']).upper()
                except Exception:
                    errors.append('Invalid device state received.')
                else:
                    if DeviceState.has_name(state):
                        data['state'] = DeviceState[state]
                    else:
                        errors.append('Invalid device state received.')
        else:
            if new_entry:
                errors.append('Required field state not found')
        if 'device_type' in kwargs:
            if isinstance(kwargs['device_type'], DeviceType):
                data['device_type'] = kwargs['device_type']
            else:
                try:
                    devicetype = str(kwargs['device_type']).upper()
                except Exception:
                    errors.append('Invalid device type')
                else:
                    if DeviceType.has_name(devicetype):
                        data['device_type'] = devicetype
                    else:
                        errors.append('Invalid device type')
        else:
            if new_entry:
                errors.append('Required field device_type not found')
        if 'port' in kwargs:
            if kwargs['port']:
                try:
                    port = int(kwargs['port'])
                except Exception:
                    errors.append('Invalid port recevied, must be an integer.')
                else:
                    data['port'] = port
            else:
                data['port'] = None
        if 'is_stack' in kwargs:
            if isinstance(kwargs['is_stack'], bool):
                data['is_stack'] = kwargs['is_stack']
            else:
                errors.append("Invalid is_stack received, must be bool")

        for k, v in kwargs.items():
            if k not in cls.__table__.columns:
                errors.append("Unknown attribute '{}' for device".format(k))

        return data, errors


@event.listens_for(Device, 'after_update')
def after_update_device(mapper, connection, target: Device):
    update_data = {
        "action": "UPDATED",
        "device_id": target.id,
        "hostname": target.hostname,
        "object": target.as_dict()
    }
    json_data = json.dumps(update_data)
    add_event(json_data=json_data, event_type="update", update_type="device")
