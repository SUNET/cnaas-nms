from __future__ import annotations

import ipaddress
import datetime
import enum
import re
from typing import Optional, List

from sqlalchemy import Column, Integer, Unicode, String, UniqueConstraint
from sqlalchemy import Enum, DateTime, Boolean
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy_utils import IPAddressType

import cnaas_nms.db.base
import cnaas_nms.db.site

from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.groups import Groups, DeviceGroups
from cnaas_nms.db.session import sqla_session
from cnaas_nms.api.generic import build_filter


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
    serial = Column(String(64))
    ztp_mac = Column(String(12))
    platform = Column(String(64))
    vendor = Column(String(64))
    model = Column(String(64))
    os_version = Column(String(64))
    synchronized = Column(Boolean, default=False)
    state = Column(Enum(DeviceState), nullable=False)  # type: ignore
    device_type = Column(Enum(DeviceType), nullable=False)
    config_hash = Column(String(64))  # SHA256 = 64 characters
    last_seen = Column(DateTime, default=datetime.datetime.now)  # onupdate=now

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
        """Look up neighbors from Linknets and return them as a list of Device objects."""
        linknets = self.get_linknets(session)
        ret = []
        for linknet in linknets:
            if linknet.device_a_id == self.id:
                ret.append(session.query(Device).filter(Device.id == linknet.device_b_id).one())
            else:
                ret.append(session.query(Device).filter(Device.id == linknet.device_a_id).one())
        return ret

    def get_linknets(self, session):
        """Look up linknets and return a list of Linknet objects."""
        ret = []
        linknets = session.query(Linknet).\
            filter(
                (Linknet.device_a_id == self.id)
                |
                (Linknet.device_b_id == self.id)
            )
        for linknet in linknets:
            ret.append(linknet)
        return ret

    def get_link_to(self, session, peer_device: Device) -> Optional[Linknet]:
        return session.query(Linknet).\
            filter(
                ((Linknet.device_a_id == self.id) & (Linknet.device_b_id == peer_device.id))
                |
                ((Linknet.device_b_id == self.id) & (Linknet.device_a_id == peer_device.id))
            ).one_or_none()

    def get_link_to_local_ifname(self, session, peer_device: Device) -> Optional[str]:
        """Get the local interface name on this device that links to peer_device."""
        linknet = self.get_link_to(session, peer_device)
        if not linknet:
            return None
        if linknet.device_a_id == self.id:
            return linknet.device_a_port
        elif linknet.device_b_id == self.id:
            return linknet.device_b_port

    @classmethod
    def valid_hostname(cls, hostname: str) -> bool:
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
    def device_add(cls, **kwargs):
        data, errors = cls.validate(**kwargs)
        if errors != []:
            return errors
        with sqla_session() as session:
            new_device = Device()
            for _ in data:
                setattr(new_device, _, data[_])
            session.add(new_device)

    @classmethod
    def device_get(cls, hostname=''):
        result = []
        with sqla_session() as session:
            if hostname != '':
                instance: Device = session.query(Device).filter(Device.hostname ==
                                                                hostname).one_or_none()
                return instance.id
            else:
                query = session.query(Device)
                query = build_filter(Device, query)
                for instance in query:
                    result.append(instance.as_dict())
        return result

    @classmethod
    def device_update(cls, device_id, **kwargs):
        data, error = cls.validate(**kwargs)
        if error != []:
            return error
        with sqla_session() as session:
            instance: Device = session.query(Device).filter(Device.id ==
                                                            device_id).one_or_none()
            if not instance:
                return ['Device not found']
            for _ in data:
                setattr(instance, _, data[_])

    @classmethod
    def device_groups_add(cls, **kwargs):
        data, error = cls.validate(**kwargs)
        if error != []:
            return error
        fields = kwargs['hostname'].split('.')
        if len(fields) < 5:
            return error
        site = fields[0]
        device_type = fields[1]
        building = fields[2]
        floor = fields[3]
        index = fields[4]
        device_id = Device.device_get(hostname=kwargs['hostname'])
        if not Groups.group_get(index=0, name=site):
            Groups.group_add(site)
        cls.device_group_add(site, device_id)
        if not Groups.group_get(index=0, name=device_type):
            Groups.group_add(device_type)
        cls.device_group_add(device_type, device_id)
        if not Groups.group_get(index=0, name=building):
            Groups.group_add(building)
        cls.device_group_add(building, device_id)
        if not Groups.group_get(index=0, name=floor):
            Groups.group_add(floor)
        cls.device_group_add(floor, device_id)
        if not Groups.group_get(index=0, name=index):
            Groups.group_add(index)
        cls.device_group_add(index, device_id)

    @classmethod
    def device_group_add(cls, name, index):
        with sqla_session() as session:
            instance: Groups = session.query(Groups).filter(Groups.name ==
                                                            name).one_or_none()
            if not instance:
                return empty_result(status='error', data='Group not found'), 404
            group = instance.as_dict()
            instance: Device = session.query(Device).filter(Device.id ==
                                                            index).one_or_none()
            if not instance:
                return 'Could not find device'
            device = instance.as_dict()
            device_groups = DeviceGroups()
            device_groups.device_id = device['id']
            device_groups.groups_id = group['id']
            session.add(device_groups)
        return None

    @classmethod
    def validate(cls, **kwargs):
        data = {}
        errors = []
        if 'hostname' in kwargs:
            if Device.valid_hostname(kwargs['hostname']):
                data['hostname'] = kwargs['hostname']
            else:
                errors.append("Invalid hostname received")
        else:
            errors.append('Required ifeld hostname not found')

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
            try:
                addr = ipaddress.IPv4Address(kwargs['management_ip'])
            except Exception:
                errors.append('Invalid management_ip received. Must be correct IPv4 address.')
            else:
                data['management_ip'] = addr
        else:
            data['management_ip'] = None

        if 'dhcp_ip' in kwargs:
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
            errors.append('Required field device_state not found')
        if 'device_type' in kwargs:
            try:
                devicetype = str(kwargs['device_type']).upper()
            except Exception:
                errors.append('Invalid device type')
            else:
                if DeviceType.has_name(devicetype):
                    data['device_type'] = kwargs['device_type']
                else:
                    errors.append('Invalid device type')
        else:
            errors.append('Required field device_type not found')

        return data, errors
