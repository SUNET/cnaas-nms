import datetime
from typing import Optional, List, Dict

from nornir_napalm.plugins.tasks import napalm_get

from cnaas_nms.confpush.underlay import find_free_infra_linknet
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import Device, DeviceType, DeviceState
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.confpush.get import get_interfaces_names, get_uplinks, \
    filter_interfaces, get_mlag_ifs, get_neighbors, verify_peer_iftype
from cnaas_nms.db.settings import get_settings
from cnaas_nms.tools.log import get_logger
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.confpush.nornir_helper import NornirJobResult
from cnaas_nms.scheduler.jobresult import DictJobResult
import cnaas_nms.confpush.nornir_helper


def update_interfacedb_worker(session, dev: Device, replace: bool, delete_all: bool,
                              mlag_peer_hostname: Optional[str] = None,
                              linknets: Optional[List[dict]] = None) -> List[dict]:
    """Perform actual work of updating database for update_interfacedb.
    If replace is set to true, configtype and data will get overwritten.
    If delete_all is set to true, delete all interfaces from database.
    Return list of new/updated interfaces, or empty if delete_all was set."""
    logger = get_logger()
    ret = []

    current_iflist = session.query(Interface).filter(Interface.device == dev).all()
    unmatched_iflist = []
    current_intf: Interface
    for current_intf in current_iflist:
        if delete_all:
            logger.debug("Deleting interface {} on device {} from interface DB".format(
                current_intf.name, dev.hostname
            ))
            session.delete(current_intf)
        else:
            unmatched_iflist.append(current_intf)
    if delete_all:
        session.commit()
        return ret

    iflist = get_interfaces_names(dev.hostname)  # query nornir for current interfaces
    uplinks = get_uplinks(session, dev.hostname, recheck=replace, linknets=linknets)
    if mlag_peer_hostname:
        mlag_ifs = get_mlag_ifs(session, dev.hostname, mlag_peer_hostname, linknets=linknets)
    else:
        mlag_ifs = {}
    phy_interfaces = filter_interfaces(iflist, platform=dev.platform, include='physical')
    if not phy_interfaces:
        raise Exception("Could not find any physical interfaces for device {}".format(dev.hostname))

    for intf_name in phy_interfaces:
        intf: Interface = session.query(Interface).filter(Interface.device == dev). \
            filter(Interface.name == intf_name).one_or_none()
        if intf in unmatched_iflist:
            unmatched_iflist.remove(intf)
        if intf:
            new_intf = False
        else:
            new_intf = True
            intf: Interface = Interface()
        if not new_intf and not replace:
            continue
        logger.debug("New/updated physical interface found on device {}: {}".format(
            dev.hostname, intf_name
        ))
        if intf_name in uplinks.keys():
            intf.configtype = InterfaceConfigType.ACCESS_UPLINK
            intf.data = {'neighbor': uplinks[intf_name]}
        elif intf_name in mlag_ifs.keys():
            intf.configtype = InterfaceConfigType.MLAG_PEER
            intf.data = {'neighbor_id': mlag_ifs[intf_name]}
        else:
            intf.configtype = InterfaceConfigType.ACCESS_AUTO
        intf.name = intf_name
        intf.device = dev
        if new_intf:
            session.add(intf)
        ret.append(intf.as_dict())

    # Remove interfaces that no longer exist on device
    for unmatched_intf in unmatched_iflist:
        protected_interfaces = [InterfaceConfigType.ACCESS_UPLINK,
                                InterfaceConfigType.MLAG_PEER]
        if unmatched_intf.configtype in protected_interfaces:
            logger.warn("Interface of protected type disappeared from {} ignoring: {}".format(
                dev.hostname, unmatched_intf.name
            ))
        else:
            logger.info("Deleting interface {} from {} because it disappeared on device".format(
                unmatched_intf.name, dev.hostname
            ))
            session.delete(unmatched_intf)
    session.commit()
    return ret


@job_wrapper
def update_interfacedb(hostname: str, replace: bool = False, delete_all: bool = False,
                       mlag_peer_hostname: Optional[str] = None,
                       job_id: Optional[str] = None,
                       scheduled_by: Optional[str] = None) -> DictJobResult:
    """Update interface DB with any new physical interfaces for specified device.
    If replace is set, any existing records in the database will get overwritten.
    If delete_all is set, all entries in database for this device will be removed.

    Returns:
        List of interfaces that was added to DB
    """
    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            raise ValueError(f"Hostname {hostname} not found in database")
        if dev.state != DeviceState.MANAGED:
            raise ValueError(f"Hostname {hostname} is not a managed device")
        if dev.device_type != DeviceType.ACCESS:
            raise ValueError("This function currently only supports access devices")

        result = update_interfacedb_worker(session, dev, replace, delete_all, mlag_peer_hostname)

        if result:
            dev.synchronized = False
    return DictJobResult(result={"interfaces": result})


def reset_interfacedb(hostname: str):
    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            raise ValueError(f"Hostname {hostname} not found in database")

        ret = session.query(Interface).filter(Interface.device == dev).delete()
        return ret


def set_facts(dev: Device, facts: dict) -> dict:
    attr_map = {
        # Map NAPALM getfacts name -> device.Device member name
        'vendor': 'vendor',
        'model': 'model',
        'os_version': 'os_version',
        'serial_number': 'serial',
    }
    diff = {}
    # Update any attributes that has changed
    for dict_key, obj_member in attr_map.items():
        obj_data = dev.__getattribute__(obj_member)
        maxlen = Device.__dict__[obj_member].property.columns[0].type.length
        fact_data = facts[dict_key][:maxlen]
        if fact_data and obj_data != fact_data:
            diff[obj_member] = {
                'old': obj_data,
                'new': fact_data
            }
            dev.__setattr__(obj_member, fact_data)
    return diff


@job_wrapper
def update_facts(hostname: str,
                 job_id: Optional[str] = None,
                 scheduled_by: Optional[str] = None):
    logger = get_logger()
    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            raise ValueError("Device with hostname {} not found".format(hostname))
        if not (dev.state == DeviceState.MANAGED or dev.state == DeviceState.UNMANAGED):
            raise ValueError("Device with hostname {} is in incorrect state: {}".format(
                hostname, str(dev.state)
            ))
        hostname = dev.hostname

    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)

    nrresult = nr_filtered.run(task=napalm_get, getters=["facts"])

    if nrresult.failed:
        logger.error("Could not contact device with hostname {}".format(hostname))
        return NornirJobResult(nrresult=nrresult)
    try:
        facts = nrresult[hostname][0].result['facts']
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
            diff = set_facts(dev, facts)
            dev.last_seen = datetime.datetime.utcnow()

        logger.debug("Updating facts for device {}, new values: {}, {}, {}, {}".format(
            hostname, facts['serial_number'], facts['vendor'], facts['model'], facts['os_version']
        ))
    except Exception as e:
        logger.exception("Could not update device with hostname {} with new facts: {}".format(
            hostname, str(e)
        ))
        logger.debug("Get facts nrresult for hostname {}: {}".format(hostname, nrresult))
        raise e

    return DictJobResult(result={"diff": diff})


def update_linknets(session, hostname: str, devtype: DeviceType,
                    ztp_hostname: Optional[str] = None,
                    mlag_peer_dev: Optional[Device] = None, dry_run: bool = False,
                    neighbors_arg: Optional[Dict[str, list]] = None) -> List[dict]:
    """Update linknet data for specified device using LLDP neighbor data.

    Returns:
        List[dict]: List of linknets as dict, extra field redundant_link
                    added in each dict defaults to true

    Raises:
        InterfaceError: incompatible interfaces found by verify_peer_iftype
    """
    logger = get_logger()
    if neighbors_arg:
        neighbors = neighbors_arg
    else:
        result = get_neighbors(hostname=hostname)[hostname][0]
        if result.failed:
            raise Exception("Could not get LLDP neighbors for {}".format(hostname))
        neighbors = result.result['lldp_neighbors']
    if ztp_hostname:
        settings_hostname = ztp_hostname
    else:
        settings_hostname = hostname

    ret = []

    local_device_inst: Device = session.query(Device).filter(Device.hostname == hostname).one()
    logger.debug("Updating linknets for device id {} ({}) of type {}...".format(
        local_device_inst.id, settings_hostname, devtype.name))

    for local_if, data in neighbors.items():
        logger.debug(f"Local: {local_if}, remote: {data[0]['hostname']} {data[0]['port']}")
        remote_device_inst: Device = session.query(Device).\
            filter(Device.hostname == data[0]['hostname']).one_or_none()
        if not remote_device_inst:
            logger.debug(f"Unknown neighbor device, ignoring: {data[0]['hostname']}")
            continue
        if remote_device_inst.id == mlag_peer_dev.id:
            # In case of MLAG init the peer does not have the correct devtype set yet,
            # use same devtype as local device instead
            remote_devtype = devtype
        elif remote_device_inst.state not in [DeviceState.MANAGED, DeviceState.UNMANAGED]:
            logger.debug("Neighbor device has invalid state, ignoring: {}".format(
                data[0]['hostname']))
            continue
        else:
            remote_devtype = remote_device_inst.device_type

        logger.debug(f"Remote device found, device id: {remote_device_inst.id}")

        local_device_settings, _ = get_settings(settings_hostname,
                                                devtype,
                                                local_device_inst.model
                                                )
        remote_device_settings, _ = get_settings(remote_device_inst.hostname,
                                                 remote_devtype,
                                                 remote_device_inst.model
                                                 )

        local_device_inst_copy = Device(
            hostname=local_device_inst.hostname,
            device_type=local_device_inst.device_type
        )
        local_device_inst_copy.device_type = devtype
        redundant_link = verify_peer_iftype(
            session,
            local_device_inst_copy, local_device_settings, local_if,
            remote_device_inst, remote_device_settings, data[0]['port'])

        # Check if linknet object already exists in database
        local_devid = local_device_inst.id
        check_linknet = session.query(Linknet).\
            filter(
                ((Linknet.device_a_id == local_devid) & (Linknet.device_a_port == local_if))
                |
                ((Linknet.device_b_id == local_devid) & (Linknet.device_b_port == local_if))
                |
                ((Linknet.device_a_id == remote_device_inst.id) &
                 (Linknet.device_a_port == data[0]['port']))
                |
                ((Linknet.device_b_id == remote_device_inst.id) &
                 (Linknet.device_b_port == data[0]['port']))
            ).one_or_none()
        if check_linknet:
            logger.debug(f"Found existing linknet id: {check_linknet.id}")
            if (
                    (
                        check_linknet.device_a_id == local_devid
                        and check_linknet.device_a_port == local_if
                        and check_linknet.device_b_id == remote_device_inst.id
                        and check_linknet.device_b_port == data[0]['port']
                    )
                    or
                    (
                        check_linknet.device_a_id == local_devid
                        and check_linknet.device_a_port == local_if
                        and check_linknet.device_b_id == remote_device_inst.id
                        and check_linknet.device_b_port == data[0]['port']
                    )
            ):
                if not dry_run:
                    if check_linknet.device_a_id == local_devid:
                        ret_dict = {
                            'device_a_hostname': local_device_inst.hostname,
                            'device_a_id': local_device_inst.id,
                            'device_b_hostname': remote_device_inst.hostname,
                            'device_b_id': remote_device_inst.id,
                        }
                    else:
                        ret_dict = {
                            'device_a_hostname': remote_device_inst.hostname,
                            'device_a_id': remote_device_inst.id,
                            'device_b_hostname': local_device_inst.hostname,
                            'device_b_id': local_device_inst.id,
                        }
                    ret_dict = {
                        **ret_dict,
                        'redundant_link': redundant_link,
                        **check_linknet.as_dict()
                    }
                    del ret_dict['id']
                    ret.append({k: ret_dict[k] for k in sorted(ret_dict)})
                    # All info is the same, no update required
                    continue
            else:
                # TODO: update instead of delete+new insert?
                if not dry_run:
                    session.delete(check_linknet)
                    session.commit()

        if devtype in [DeviceType.CORE, DeviceType.DIST] and \
                remote_device_inst.device_type in [DeviceType.CORE, DeviceType.DIST]:
            ipv4_network = find_free_infra_linknet(session)
        else:
            ipv4_network = None
        new_link = Linknet.create_linknet(
            session,
            hostname_a=local_device_inst.hostname,
            interface_a=local_if,
            hostname_b=remote_device_inst.hostname,
            interface_b=data[0]['port'],
            ipv4_network=ipv4_network,
            strict_check=not dry_run  # Don't do strict check if this is a dry_run
        )
        if not dry_run:
            session.add(new_link)
            session.commit()
        else:
            # Make sure linknet object is not added to session because of foreign key load
            session.expunge(new_link)
        # Make return data pretty
        ret_dict = {
            **new_link.as_dict(),
            'device_a_hostname': local_device_inst.hostname,
            'device_a_id': local_device_inst.id,
            'device_b_hostname': remote_device_inst.hostname,
            'device_b_id': remote_device_inst.id,
            'redundant_link': redundant_link,
        }
        del ret_dict['id']
        ret.append({k: ret_dict[k] for k in sorted(ret_dict)})
    return ret
