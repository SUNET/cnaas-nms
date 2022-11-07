import datetime
import os
from typing import Optional, List
from ipaddress import IPv4Interface, IPv4Address

from nornir_napalm.plugins.tasks import napalm_configure, napalm_get
from nornir_jinja2.plugins.tasks import template_file
from nornir_utils.plugins.functions import print_result
from nornir.core.task import Result
from nornir.core.exceptions import NornirSubTaskError
from netmiko.exceptions import ReadTimeout as NMReadTimeout
from apscheduler.job import Job
import yaml

import cnaas_nms.confpush.nornir_helper
import cnaas_nms.confpush.get
import cnaas_nms.confpush.underlay
import cnaas_nms.db.helper
from cnaas_nms.app_settings import api_settings, app_settings
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import Device, DeviceState, DeviceType, \
    DeviceError, DeviceStateError, DeviceSyncError
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.confpush.nornir_helper import NornirJobResult, get_jinja_env
from cnaas_nms.confpush.update import update_interfacedb_worker, update_linknets, set_facts
from cnaas_nms.confpush.sync_devices import populate_device_vars, confcheck_devices
from cnaas_nms.db.git import RepoStructureException
from cnaas_nms.plugins.pluginmanager import PluginManagerHandler
from cnaas_nms.db.reservedip import ReservedIP
from cnaas_nms.tools.log import get_logger
from cnaas_nms.scheduler.thread_data import set_thread_data
from cnaas_nms.tools.pki import generate_device_cert
from cnaas_nms.confpush.cert import arista_copy_cert


class ConnectionCheckError(Exception):
    pass


class InitVerificationError(Exception):
    pass


class InitError(Exception):
    pass


class NeighborError(Exception):
    pass


def push_base_management(task, device_variables: dict, devtype: DeviceType, job_id):
    set_thread_data(job_id)
    logger = get_logger()
    logger.debug("Push basetemplate for host: {}".format(task.host.name))
    local_repo_path = app_settings.TEMPLATES_LOCAL

    mapfile = os.path.join(local_repo_path, task.host.platform, 'mapping.yml')
    if not os.path.isfile(mapfile):
        raise RepoStructureException("File {} not found in template repo".format(mapfile))
    with open(mapfile, 'r') as f:
        mapping = yaml.safe_load(f)
        template = mapping[devtype.name]['entrypoint']

    # TODO: install device certificate, using new hostname and reserved IP.
    #       exception on fail if tls_verify!=False
    try:
        device_cert_res = task.run(
            task=ztp_device_cert,
            job_id=job_id,
            new_hostname=task.host.name,
            management_ip=device_variables['mgmt_ip']
        )
    except NornirSubTaskError as e:
        try:
            assert not type(e.result[1][1].exception) is NMReadTimeout
        except AssertionError:
            logger.error("Read timeout while copying cert to device")
        except (AttributeError, IndexError) as e:
            pass
        logger.exception(e)
    except Exception as e:
        logger.exception(e)
    else:
        if device_cert_res.failed:
            if api_settings.VERIFY_TLS_DEVICE:
                logger.error("Unable to install device certificate for {}, aborting".format(
                    device_variables['host']))
                raise Exception(device_cert_res[0].exception)
            else:
                logger.debug("Unable to install device certificate for {}".format(
                    device_variables['host']))

    r = task.run(task=template_file,
                 name="Generate initial device config",
                 template=template,
                 jinja_env=get_jinja_env(f"{local_repo_path}/{task.host.platform}"),
                 path=f"{local_repo_path}/{task.host.platform}",
                 **device_variables)

    #TODO: Handle template not found, variables not defined

    task.host["config"] = r.result
    # Use extra low timeout for this since we expect to loose connectivity after changing IP
    connopts_napalm = task.host.connection_options["napalm"]
    connopts_napalm.extras["timeout"] = api_settings.INIT_MGMT_TIMEOUT

    try:
        task.run(task=napalm_configure,
                 name="Push base management config",
                 replace=True,
                 configuration=task.host["config"],
                 dry_run=False
                 )
    except Exception:
        task.run(task=napalm_get, getters=["facts"])
        if not task.results[-1].failed:
            raise InitError("Device {} did not commit new base management config".format(
                task.host.name
            ))


def pre_init_checks(session, device_id) -> Device:
    """Find device with device_id and check that it's ready for init, returns
    Device object or raises exception"""
    # Check that we can find device and that it's in the correct state to start init
    dev: Device = session.query(Device).filter(Device.id == device_id).one_or_none()
    if not dev:
        raise ValueError(f"No device with id {device_id} found")
    if dev.state != DeviceState.DISCOVERED:
        raise DeviceStateError("Device must be in state DISCOVERED to begin init")
    old_hostname = dev.hostname
    # Perform connectivity check
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_old_filtered = nr.filter(name=old_hostname)
    try:
        nrresult_old = nr_old_filtered.run(task=napalm_get, getters=["facts"])
    except Exception as e:
        raise ConnectionCheckError(f"Failed to connect to device_id {device_id}: {str(e)}")
    if nrresult_old.failed:
        print_result(nrresult_old)
        raise ConnectionCheckError(f"Failed to connect to device_id {device_id}")
    return dev


def pre_init_check_neighbors(session, dev: Device, devtype: DeviceType,
                             linknets: List[dict],
                             expected_neighbors: Optional[List[str]] = None,
                             mlag_peer_dev: Optional[Device] = None) -> List[str]:
    """Check for compatible neighbors
    Args:
        session: SQLAlchemy session
        dev: Device object to check
        devtype: The target device type (not the same as current during init)
        linknets: List of linknets to check for compatible neighbors
        expected_neighbors: Optional list to manually specify neighbors
        mlag_peer_dev: Optional device that is the MLAG peer
    Returns:
        List of compatible neighbor hostnames
    Raises:
        NeighborError: Neighbor not found
        Exception: Generic error
        InitVerificationError:
    """
    logger = get_logger()
    verified_neighbors = []
    if expected_neighbors is not None and len(expected_neighbors) == 0:
        logger.debug("expected_neighbors explicitly set to empty list, skipping neighbor checks")
        return []
    if not linknets:
        raise Exception("No linknets were specified to check_neighbors")

    if devtype == DeviceType.ACCESS:
        neighbors = []
        uplinks = []
        mlag_peers = []
        redundant_uplinks = 0
        for linknet in linknets:
            if linknet['device_a_hostname'] == linknet['device_b_hostname']:
                continue  # don't add loopback cables as neighbors
            elif linknet['device_a_hostname'] == dev.hostname:
                neighbor = linknet['device_b_hostname']
            elif linknet['device_b_hostname'] == dev.hostname:
                neighbor = linknet['device_a_hostname']
            elif mlag_peer_dev:
                if linknet['device_a_hostname'] == mlag_peer_dev.hostname:
                    neighbor = linknet['device_b_hostname']
                elif linknet['device_b_hostname'] == mlag_peer_dev.hostname:
                    neighbor = linknet['device_a_hostname']
            else:
                raise Exception("Own hostname not found in linknet")
            neighbor_dev: Device = session.query(Device). \
                filter(Device.hostname == neighbor).one_or_none()
            if not neighbor_dev:
                raise NeighborError("Neighbor device {} not found in database".format(neighbor))

            if mlag_peer_dev and mlag_peer_dev == neighbor_dev:
                mlag_peers.append(neighbor)
            elif neighbor_dev.device_type in [DeviceType.ACCESS, DeviceType.DIST]:
                if 'redundant_link' in linknet:
                    if linknet['redundant_link']:
                        redundant_uplinks += 1
                else:
                    redundant_uplinks += 1
                uplinks.append(neighbor)

            neighbors.append(neighbor)

        if len(uplinks) <= 0:
            raise InitVerificationError(
                "No uplink neighbors found for device id: {} ({})".format(dev.id, dev.hostname))
        elif len(uplinks) == 1 and redundant_uplinks == 0:
            logger.debug(
                "One non-redundant uplink neighbors found for device id {} ({}): {}".format(
                    dev.id, dev.hostname, uplinks
                ))
        elif len(uplinks) == 2 and redundant_uplinks == 2:
            logger.debug(
                "Two redundant uplink neighbors found for device id {} ({}): {}".format(
                    dev.id, dev.hostname, uplinks
                ))
        else:
            raise InitVerificationError(
                ("Incompatible uplink neighbors found for device id {} ({}): "
                 """{} - {} has redundancy required ("redundant_link" setting)""").format(
                    dev.id, dev.hostname, uplinks, redundant_uplinks
                ))

        if mlag_peer_dev and len(mlag_peers) < 2:
            raise InitVerificationError(
                ("MLAG requires at least two MLAG peer links, {} found for"
                 "device id {} ({})").format(
                    len(mlag_peers), dev.id, dev.hostname
                ))

        try:
            cnaas_nms.db.helper.find_mgmtdomain(session, uplinks)
        except Exception as e:
            raise InitVerificationError(str(e))
        else:
            verified_neighbors = neighbors
    elif devtype in [DeviceType.CORE, DeviceType.DIST]:
        for linknet in linknets:
            if linknet['device_a_hostname'] == dev.hostname:
                neighbor = linknet['device_b_hostname']
            elif linknet['device_b_hostname'] == dev.hostname:
                neighbor = linknet['device_a_hostname']
            else:
                raise Exception("Own hostname not found in linknet")
            if expected_neighbors:
                if neighbor in expected_neighbors:
                    verified_neighbors.append(neighbor)
                # Neighbor was explicitly set -> skip verification of neighbor devtype
                continue

            neighbor_dev: Device = session.query(Device).\
                filter(Device.hostname == neighbor).one_or_none()
            if not neighbor_dev:
                raise NeighborError("Neighbor device {} not found in database".format(neighbor))
            if devtype == DeviceType.CORE:
                if neighbor_dev.device_type == DeviceType.DIST:
                    verified_neighbors.append(neighbor)
                else:
                    logger.warn("Neighbor device {} is of unexpected device type {}, ignoring".format(
                        neighbor, neighbor_dev.device_type.name
                    ))
            else:
                if neighbor_dev.device_type == DeviceType.CORE:
                    verified_neighbors.append(neighbor)
                else:
                    logger.warn("Neighbor device {} is of unexpected device type {}, ignoring".format(
                        neighbor, neighbor_dev.device_type.name
                    ))

        if expected_neighbors:
            if len(expected_neighbors) != len(verified_neighbors):
                raise InitVerificationError("Not all expected neighbors were detected")
        else:
            if len(verified_neighbors) < 2:
                raise InitVerificationError("Not enough compatible neighbors ({} of 2) were detected".format(
                    len(verified_neighbors)
                ))
    return verified_neighbors


def pre_init_check_mlag(session, dev, mlag_peer_dev):
    intfs: Interface = session.query(Interface).filter(Interface.device == dev).\
        filter(InterfaceConfigType == InterfaceConfigType.MLAG_PEER).all()
    intf: Interface
    for intf in intfs:
        if intf.data['neighbor_id'] == mlag_peer_dev.id:
            continue
        else:
            raise Exception("Inconsistent MLAG peer {} detected for device {}".format(
                intf.data['neighbor'], dev.hostname
            ))


def ztp_device_cert(task, job_id: str, new_hostname: str, management_ip: str) -> str:
    set_thread_data(job_id)
    logger = get_logger()

    try:
        ipv4: IPv4Address = IPv4Address(management_ip)
        generate_device_cert(new_hostname, ipv4_address=ipv4)
    except Exception as e:
        raise Exception("Could not generate certificate for device {}: {}".format(
            new_hostname, e
        ))

    if task.host.platform == "eos":
        try:
            # TODO: subtaskerror?
            res = task.run(task=arista_copy_cert,
                           job_id=job_id)
        except Exception as e:
            logger.exception('Exception while copying certificates: {}'.format(
                str(e)))
            raise e
    else:
        return "Install device certificate not supported on platform: {}".format(
            task.host.platform
        )
    return "Device certificate installed for {}".format(new_hostname)


@job_wrapper
def init_access_device_step1(device_id: int, new_hostname: str,
                             mlag_peer_id: Optional[int] = None,
                             mlag_peer_new_hostname: Optional[str] = None,
                             uplink_hostnames_arg: Optional[List[str]] = [],
                             job_id: Optional[str] = None,
                             scheduled_by: Optional[str] = None) -> NornirJobResult:
    """Initialize access device for management by CNaaS-NMS.
    If a MLAG/MC-LAG pair is to be configured both mlag_peer_id and
    mlag_peer_new_hostname must be set.

    Args:
        device_id: Device to select for initialization
        new_hostname: Hostname to configure on this device
        mlag_peer_id: Device ID of MLAG peer device (optional)
        mlag_peer_new_hostname: Hostname to configure on peer device (optional)
        uplink_hostnames_arg: List of hostnames of uplink peer devices (optional)
                              Used when initializing MLAG peer device
        job_id: job_id provided by scheduler when adding job
        scheduled_by: Username from JWT.

    Returns:
        Nornir result object

    Raises:
        DeviceStateException
        ValueError
    """
    logger = get_logger()
    with sqla_session() as session:
        dev = pre_init_checks(session, device_id)
        linknets_all = dev.get_linknets_as_dict(session)
        mlag_peer_dev: Optional[Device] = None

        # update linknets using LLDP data
        linknets_all += update_linknets(session, dev.hostname, DeviceType.ACCESS, dry_run=True)

        # If this is the first device in an MLAG pair
        if mlag_peer_id and mlag_peer_new_hostname:
            mlag_peer_dev = pre_init_checks(session, mlag_peer_id)
            linknets_all += mlag_peer_dev.get_linknets_as_dict(session)
            linknets_all += update_linknets(session, mlag_peer_dev.hostname, DeviceType.ACCESS, dry_run=True)
            update_interfacedb_worker(session, dev, replace=True, delete_all=False,
                                      mlag_peer_hostname=mlag_peer_dev.hostname, linknets=linknets_all)
            update_interfacedb_worker(session, mlag_peer_dev, replace=True, delete_all=False,
                                      mlag_peer_hostname=dev.hostname, linknets=linknets_all)
            uplink_hostnames = dev.get_uplink_peer_hostnames(session)
            uplink_hostnames += mlag_peer_dev.get_uplink_peer_hostnames(session)
            # check that both devices see the correct MLAG peer
            pre_init_check_mlag(session, dev, mlag_peer_dev)
            pre_init_check_mlag(session, mlag_peer_dev, dev)
        # If this is the second device in an MLAG pair
        elif uplink_hostnames_arg:
            uplink_hostnames = uplink_hostnames_arg
        elif mlag_peer_id or mlag_peer_new_hostname:
            raise ValueError("mlag_peer_id and mlag_peer_new_hostname must be specified together")
        # If this device is not part of an MLAG pair
        else:
            update_interfacedb_worker(session, dev, replace=True, delete_all=False, linknets=linknets_all)
            uplink_hostnames = dev.get_uplink_peer_hostnames(session)

        try:
            linknets = Linknet.deduplicate_linknet_dicts(linknets_all)
            # Verify uplink neighbors only for first device in MLAG pair
            if not uplink_hostnames_arg:
                verified_neighbors = pre_init_check_neighbors(
                    session, dev, DeviceType.ACCESS, linknets, mlag_peer_dev=mlag_peer_dev)
                logger.debug("Found valid neighbors for INIT of {}: {}".format(
                    new_hostname, ", ".join(verified_neighbors)
                ))
                check_neighbor_sync(session, uplink_hostnames)
        except DeviceSyncError as e:
            logger.warn("Uplink device not in sync during init of {}: {}".format(
                new_hostname, e
            ))
        except (Exception, NeighborError) as e:
            session.rollback()
            raise e

        try:
            update_linknets(session, dev.hostname, DeviceType.ACCESS, dry_run=False)
            if mlag_peer_dev:
                update_linknets(session, mlag_peer_dev.hostname, DeviceType.ACCESS, dry_run=False)
        except Exception as e:
            session.rollback()
            raise e

        # TODO: check compatability, same dist pair and same ports on dists
        mgmtdomain = cnaas_nms.db.helper.find_mgmtdomain(session, uplink_hostnames)
        if not mgmtdomain:
            raise Exception(
                "Could not find appropriate management domain for uplink peer devices: {}".format(
                    uplink_hostnames))
        # Select a new management IP for the device
        ReservedIP.clean_reservations(session, device=dev)
        session.commit()
        mgmt_ip = mgmtdomain.find_free_mgmt_ip(session)
        if not mgmt_ip:
            raise Exception("Could not find free management IP for management domain {}/{}".format(
                mgmtdomain.id, mgmtdomain.description))
        reserved_ip = ReservedIP(device=dev, ip=mgmt_ip)
        session.add(reserved_ip)
        session.commit()
        # Populate variables for template rendering
        mgmt_gw_ipif = IPv4Interface(mgmtdomain.ipv4_gw)
        mgmt_variables = {
            'mgmt_ipif': str(IPv4Interface('{}/{}'.format(mgmt_ip, mgmt_gw_ipif.network.prefixlen))),
            'mgmt_ip': str(mgmt_ip),
            'mgmt_prefixlen': int(mgmt_gw_ipif.network.prefixlen),
            'mgmt_vlan_id': mgmtdomain.vlan,
            'mgmt_gw': mgmt_gw_ipif.ip,
        }
        device_variables = populate_device_vars(session, dev, new_hostname, DeviceType.ACCESS)
        device_variables = {
            **device_variables,
            **mgmt_variables
        }
        # Update device state
        old_hostname = dev.hostname
        dev.hostname = new_hostname
        session.commit()
        hostname = dev.hostname

    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)

    # step2. push management config
    nrresult = nr_filtered.run(task=push_base_management,
                               device_variables=device_variables,
                               devtype=DeviceType.ACCESS,
                               job_id=job_id)

    napalm_get_oldip_result: Result = \
        [res for res in nrresult[hostname] if res.name == "napalm_get"][0]

    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.id == device_id).one()
        # If a get call to the old IP does not fail, it means management IP change did not work
        # Abort and rollback to initial state before device_init
        if not napalm_get_oldip_result.failed:
            dev.hostname = old_hostname
            linknets = dev.get_linknets(session)
            for linknet in linknets:
                session.delete(linknet)
            reserved_ip = session.query(ReservedIP).filter(ReservedIP.device == dev).one_or_none()
            if reserved_ip:
                session.delete(reserved_ip)
            return NornirJobResult(nrresult=nrresult)

        dev.management_ip = device_variables['mgmt_ip']
        dev.state = DeviceState.INIT
        dev.device_type = DeviceType.ACCESS
        # Remove the reserved IP since it's now saved in the device database instead
        reserved_ip = session.query(ReservedIP).filter(ReservedIP.device == dev).one_or_none()
        if reserved_ip:
            session.delete(reserved_ip)
        # Mark remote peers as unsynchronized so they can update interface descriptions
        for linknet in linknets:
            if linknet['device_a_id'] == device_id:
                peer_hostname = linknet['device_b_hostname']
            else:
                peer_hostname = linknet['device_a_hostname']
            peer_dev: Device = session.query(Device).filter(Device.hostname == peer_hostname).one_or_none()
            if peer_dev:
                peer_dev.synchronized = False

    # Plugin hook, allocated IP
    try:
        pmh = PluginManagerHandler()
        pmh.pm.hook.allocated_ipv4(vrf='mgmt', ipv4_address=str(mgmt_ip),
                                   ipv4_network=str(mgmt_gw_ipif.network),
                                   hostname=hostname
                                   )
    except Exception as e:
        logger.exception("Error while running plugin hooks for allocated_ipv4: ".format(str(e)))

    # step3. register apscheduler job that continues steps
    if mlag_peer_id and mlag_peer_new_hostname:
        # account for delayed start of peer device plus mgmt timeout
        step2_delay = 60+2*api_settings.INIT_MGMT_TIMEOUT
    else:
        step2_delay = api_settings.INIT_MGMT_TIMEOUT
    scheduler = Scheduler()
    next_job_id = scheduler.add_onetime_job(
        'cnaas_nms.confpush.init_device:init_device_step2',
        when=step2_delay,
        scheduled_by=scheduled_by,
        kwargs={'device_id': device_id, 'iteration': 1})

    logger.info("Init step 2 for {} scheduled as job # {}".format(
        new_hostname, next_job_id
    ))

    if mlag_peer_id and mlag_peer_new_hostname:
        mlag_peer_job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.init_device:init_access_device_step1',
            when=60,
            scheduled_by=scheduled_by,
            kwargs={
                'device_id': mlag_peer_id,
                'new_hostname': mlag_peer_new_hostname,
                'uplink_hostnames_arg': uplink_hostnames,
                'scheduled_by': scheduled_by
            })
        logger.info("MLAG peer (id {}) init scheduled as job # {}".format(
            mlag_peer_id, mlag_peer_job_id
        ))

    for res in nrresult[hostname]:
        if res.name in ["Push base management config", "push_base_management", "napalm_get"]:
            res.failed = False

    return NornirJobResult(
        nrresult=nrresult,
        next_job_id=next_job_id
    )


def check_neighbor_sync(session, hostnames: List[str]):
    """Check neighbor status.

    Raises:
        DeviceError: Device not found
        DeviceStateError: Neighbor device not in correct state
        DeviceSyncError: Neighbor device not synchronized
    """
    for hostname in hostnames:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            raise DeviceError("Neighbor device {} not found".format(hostname))
        if not dev.state == DeviceState.MANAGED:
            raise DeviceStateError("Neighbor device {} not in state MANAGED".format(hostname))
        if not dev.synchronized:
            raise DeviceSyncError("Neighbor device {} not synchronized".format(hostname))
    confcheck_devices(hostnames)


@job_wrapper
def init_fabric_device_step1(device_id: int, new_hostname: str, device_type: str,
                             neighbors: Optional[List[str]] = [],
                             job_id: Optional[str] = None,
                             scheduled_by: Optional[str] = None) -> NornirJobResult:
    """Initialize fabric (CORE/DIST) device for management by CNaaS-NMS.

    Args:
        device_id: Device to select for initialization
        new_hostname: Hostname to configure on this device
        device_type: String representing DeviceType
        neighbors: Optional list of hostnames of peer devices
        job_id: job_id provided by scheduler when adding job
        scheduled_by: Username from JWT.

    Returns:
        Nornir result object

    Raises:
        DeviceStateException
        ValueError
    """
    logger = get_logger()
    if DeviceType.has_name(device_type):
        devtype = DeviceType[device_type]
    else:
        raise ValueError("Invalid 'device_type' provided")

    if devtype not in [DeviceType.CORE, DeviceType.DIST]:
        raise ValueError("Init fabric device requires device type DIST or CORE")

    with sqla_session() as session:
        dev = pre_init_checks(session, device_id)

        # Test update of linknets using LLDP data
        linknets = update_linknets(
            session, dev.hostname, devtype, ztp_hostname=new_hostname, dry_run=True)

        try:
            verified_neighbors = pre_init_check_neighbors(
                session, dev, devtype, linknets, neighbors)
            logger.debug("Found valid neighbors for INIT of {}: {}".format(
                new_hostname, ", ".join(verified_neighbors)
            ))
            check_neighbor_sync(session, verified_neighbors)
        except (Exception, NeighborError) as e:
            raise e

        dev.device_type = devtype
        session.commit()

        # If neighbor check works, commit new linknets
        # This will also mark neighbors as unsynced
        linknets = update_linknets(
            session, dev.hostname, devtype, ztp_hostname=new_hostname, dry_run=False)
        logger.debug("New linknets for INIT of {} created: {}".format(
            new_hostname, linknets
        ))

        # Select and reserve a new management and infra IP for the device
        ReservedIP.clean_reservations(session, device=dev)
        session.commit()

        mgmt_ip = cnaas_nms.confpush.underlay.find_free_mgmt_lo_ip(session)
        infra_ip = cnaas_nms.confpush.underlay.find_free_infra_ip(session)

        reserved_ip = ReservedIP(device=dev, ip=mgmt_ip)
        session.add(reserved_ip)
        dev.infra_ip = infra_ip
        session.commit()

        mgmt_variables = {
            'mgmt_ipif': str(IPv4Interface('{}/32'.format(mgmt_ip))),
            'mgmt_ip': str(mgmt_ip),
            'mgmt_prefixlen': 32,
            'infra_ipif': str(IPv4Interface('{}/32'.format(infra_ip))),
            'infra_ip': str(infra_ip),
        }

        device_variables = populate_device_vars(session, dev, new_hostname, devtype)
        device_variables = {
            **device_variables,
            **mgmt_variables
        }
        # Update device state
        dev.hostname = new_hostname
        session.commit()
        hostname = dev.hostname

    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)

    # step2. push management config
    nrresult = nr_filtered.run(task=push_base_management,
                               device_variables=device_variables,
                               devtype=devtype,
                               job_id=job_id)

    with sqla_session() as session:
        dev = session.query(Device).filter(Device.id == device_id).one()
        dev.management_ip = mgmt_ip
        dev.state = DeviceState.INIT
        # Remove the reserved IP since it's now saved in the device database instead
        reserved_ip = session.query(ReservedIP).filter(ReservedIP.device == dev).one_or_none()
        if reserved_ip:
            session.delete(reserved_ip)

    # Plugin hook, allocated IP
    try:
        pmh = PluginManagerHandler()
        pmh.pm.hook.allocated_ipv4(vrf='mgmt', ipv4_address=str(mgmt_ip),
                                   ipv4_network=None,
                                   hostname=hostname
                                   )
    except Exception as e:
        logger.exception("Error while running plugin hooks for allocated_ipv4: ".format(str(e)))

    # step3. resync neighbors
    scheduler = Scheduler()
    sync_nei_job_id = scheduler.add_onetime_job(
        'cnaas_nms.confpush.sync_devices:sync_devices',
        when=1,
        scheduled_by=scheduled_by,
        kwargs={'hostnames': verified_neighbors, 'dry_run': False})
    logger.info(f"Scheduled job {sync_nei_job_id} to resynchronize neighbors")

    # step4. register apscheduler job that continues steps
    scheduler = Scheduler()
    next_job_id = scheduler.add_onetime_job(
        'cnaas_nms.confpush.init_device:init_device_step2',
        when=60,
        scheduled_by=scheduled_by,
        kwargs={'device_id': device_id, 'iteration': 1})

    logger.info("Init step 2 for {} scheduled as job # {}".format(
        new_hostname, next_job_id
    ))

    return NornirJobResult(
        nrresult=nrresult,
        next_job_id=next_job_id
    )


def schedule_init_device_step2(device_id: int, iteration: int,
                               scheduled_by: str) -> Optional[int]:
    max_iterations = 2
    if iteration > 0 and iteration < max_iterations:
        scheduler = Scheduler()
        next_job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.init_device:init_device_step2',
            when=(30*iteration),
            scheduled_by=scheduled_by,
            kwargs={'device_id': device_id, 'iteration': iteration+1})
        return next_job_id
    else:
        return None


@job_wrapper
def init_device_step2(device_id: int, iteration: int = -1,
                      job_id: Optional[str] = None,
                      scheduled_by: Optional[str] = None) -> \
                      NornirJobResult:
    logger = get_logger()
    # step4+ in apjob: if success, update management ip and device state, trigger external stuff?
    with sqla_session() as session:
        dev = session.query(Device).filter(Device.id == device_id).one()
        if dev.state != DeviceState.INIT:
            logger.error("Device with ID {} got to init step2 but is in incorrect state: {}".\
                         format(device_id, dev.state.name))
            raise DeviceStateError("Device must be in state INIT to continue init step 2")
        hostname = dev.hostname
        devtype: DeviceType = dev.device_type
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)

    nrresult = nr_filtered.run(task=napalm_get, getters=["facts"])

    if nrresult.failed:
        next_job_id = schedule_init_device_step2(device_id, iteration, scheduled_by)
        if next_job_id:
            return NornirJobResult(
                nrresult=nrresult,
                next_job_id=next_job_id
            )
        else:
            return NornirJobResult(nrresult=nrresult)
    try:
        facts = nrresult[hostname][0].result['facts']
        found_hostname = facts['hostname']
    except:
        raise InitError("Could not log in to device during init step 2")
    if hostname != found_hostname:
        raise InitError("Newly initialized device presents wrong hostname")

    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.id == device_id).one()
        dev.state = DeviceState.MANAGED
        dev.synchronized = False
        set_facts(dev, facts)
        management_ip = dev.management_ip
        dev.dhcp_ip = None
        dev.last_seen = datetime.datetime.utcnow()

    # Plugin hook: new managed device
    # Send: hostname , device type , serial , platform , vendor , model , os version
    try:
        pmh = PluginManagerHandler()
        pmh.pm.hook.new_managed_device(
            hostname=hostname,
            device_type=devtype.name,
            serial_number=facts['serial_number'],
            vendor=facts['vendor'],
            model=facts['model'],
            os_version=facts['os_version'],
            management_ip=str(management_ip)
        )
    except Exception as e:
        logger.exception("Error while running plugin hooks for new_managed_device: ".format(str(e)))

    return NornirJobResult(nrresult=nrresult)


def schedule_discover_device(ztp_mac: str, dhcp_ip: str, iteration: int,
                             scheduled_by: str) -> Optional[Job]:
    max_iterations = 3
    if 0 < iteration <= max_iterations:
        scheduler = Scheduler()
        next_job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.init_device:discover_device',
            when=(60*iteration),
            scheduled_by=scheduled_by,
            kwargs={'ztp_mac': ztp_mac, 'dhcp_ip': dhcp_ip,
                    'iteration': iteration})
        return next_job_id
    else:
        return None


def set_hostname_task(task, new_hostname: str):
    local_repo_path = app_settings.TEMPLATES_LOCAL
    template_vars = {}  # host is already set by nornir
    r = task.run(
        task=template_file,
        name="Generate hostname config",
        template="hostname.j2",
        jinja_env=get_jinja_env(f"{local_repo_path}/{task.host.platform}"),
        path=f"{local_repo_path}/{task.host.platform}",
        **template_vars
    )
    task.host["config"] = r.result
    task.run(
        task=napalm_configure,
        name="Configure hostname",
        replace=False,
        configuration=task.host["config"],
    )
    task.host.close_connection("napalm")


@job_wrapper
def discover_device(ztp_mac: str, dhcp_ip: str, iteration: int,
                    job_id: Optional[str] = None,
                    scheduled_by: Optional[str] = None):
    logger = get_logger()
    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.ztp_mac == ztp_mac).one_or_none()
        if not dev:
            raise ValueError("Device with ztp_mac {} not found".format(ztp_mac))
        if dev.state != DeviceState.DHCP_BOOT:
            raise ValueError("Device with ztp_mac {} is in incorrect state: {}".format(
                ztp_mac, str(dev.state)
            ))
        if str(dev.dhcp_ip) != dhcp_ip:
            dev.dhcp_ip = dhcp_ip
        hostname = dev.hostname

    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)

    nrresult = nr_filtered.run(task=napalm_get, getters=["facts"])

    if nrresult.failed:
        logger.info("Could not contact device with ztp_mac {} (attempt {})".format(
            ztp_mac, iteration
        ))
        next_job_id = schedule_discover_device(ztp_mac, dhcp_ip, iteration+1,
                                               scheduled_by)
        if next_job_id:
            return NornirJobResult(
                nrresult=nrresult,
                next_job_id=next_job_id
            )
        else:
            return NornirJobResult(nrresult=nrresult)
    try:
        facts = nrresult[hostname][0].result['facts']
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.ztp_mac == ztp_mac).one()
            dev.serial = facts['serial_number'][:64]
            dev.vendor = facts['vendor'][:64]
            dev.model = facts['model'][:64]
            dev.os_version = facts['os_version'][:64]
            dev.state = DeviceState.DISCOVERED
            dev.last_seen = datetime.datetime.utcnow()
            new_hostname = dev.hostname
            logger.info(f"Device with ztp_mac {ztp_mac} successfully scanned" +
                        f"(attempt {iteration}), moving to DISCOVERED state")
    except Exception as e:
        logger.exception("Could not update device with ztp_mac {} with new facts: {}".format(
            ztp_mac, str(e)
        ))
        logger.debug("nrresult for ztp_mac {}: {}".format(ztp_mac, nrresult))
        raise e

    nrresult_hostname = nr_filtered.run(task=set_hostname_task, new_hostname=new_hostname)
    if nrresult_hostname.failed:
        logger.info("Could not set hostname for ztp_mac: {}".format(
            ztp_mac
        ))

    return NornirJobResult(nrresult=nrresult)
