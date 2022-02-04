import datetime
import os
from typing import Optional, List
from ipaddress import IPv4Interface, IPv4Address

from nornir_napalm.plugins.tasks import napalm_configure, napalm_get
from nornir_jinja2.plugins.tasks import template_file
from nornir_utils.plugins.functions import print_result
from apscheduler.job import Job
import yaml

import cnaas_nms.confpush.nornir_helper
import cnaas_nms.confpush.get
import cnaas_nms.confpush.underlay
import cnaas_nms.db.helper
from cnaas_nms.app_settings import api_settings
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import Device, DeviceState, DeviceType, DeviceStateException
from cnaas_nms.db.interface import Interface, InterfaceConfigType
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

    with open('/etc/cnaas-nms/repository.yml', 'r') as db_file:
        repo_config = yaml.safe_load(db_file)
        local_repo_path = repo_config['templates_local']

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
    # TODO: handle exception from ztp_device_cert -> arista_copy_cert
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
    connopts_napalm.extras["timeout"] = 30

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
        raise DeviceStateException("Device must be in state DISCOVERED to begin init")
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
    Returns:
        List of compatible neighbor hostnames
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
        for linknet in linknets:
            if linknet['device_a_hostname'] == linknet['device_b_hostname']:
                continue  # don't add loopback cables as neighbors
            elif linknet['device_a_hostname'] == dev.hostname:
                if mlag_peer_dev and linknet['device_b_hostname'] == mlag_peer_dev.hostname:
                    continue  # only add mlag peer linknet in one direction to avoid duplicate
                else:
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
                raise Exception("Neighbor device {} not found in database".format(neighbor))
            if neighbor_dev.device_type in [DeviceType.ACCESS, DeviceType.DIST]:
                uplinks.append(neighbor)

            neighbors.append(neighbor)
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
                raise Exception("Neighbor device {} not found in database".format(neighbor))
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
        new_linknets = []

        # update linknets using LLDP data
        new_linknets += update_linknets(session, dev.hostname, DeviceType.ACCESS)

        # If this is the first device in an MLAG pair
        if mlag_peer_id and mlag_peer_new_hostname:
            mlag_peer_dev = pre_init_checks(session, mlag_peer_id)
            new_linknets += update_linknets(session, mlag_peer_dev.hostname, DeviceType.ACCESS)
            update_interfacedb_worker(session, dev, replace=True, delete_all=False,
                                      mlag_peer_hostname=mlag_peer_dev.hostname)
            update_interfacedb_worker(session, mlag_peer_dev, replace=True, delete_all=False,
                                      mlag_peer_hostname=dev.hostname)
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
            update_interfacedb_worker(session, dev, replace=True, delete_all=False)
            uplink_hostnames = dev.get_uplink_peer_hostnames(session)

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

    with sqla_session() as session:
        dev = session.query(Device).filter(Device.id == device_id).one()
        dev.management_ip = device_variables['mgmt_ip']
        dev.state = DeviceState.INIT
        dev.device_type = DeviceType.ACCESS
        # Remove the reserved IP since it's now saved in the device database instead
        reserved_ip = session.query(ReservedIP).filter(ReservedIP.device == dev).one_or_none()
        if reserved_ip:
            session.delete(reserved_ip)
        # Mark remote peers as unsynchronized so they can update interface descriptions
        for linknet in new_linknets:
            peer_hostname = linknet['device_b_hostname']
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
        step2_delay = 30+60+30  # account for delayed start of peer device plus mgmt timeout
    else:
        step2_delay = 30
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

    return NornirJobResult(
        nrresult=nrresult,
        next_job_id=next_job_id
    )


def check_neighbor_sync(session, hostnames: List[str]):
    for hostname in hostnames:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            raise NeighborError("Neighbor device {} not found".format(hostname))
        if not dev.state == DeviceState.MANAGED:
            raise NeighborError("Neighbor device {} not in state MANAGED".format(hostname))
        if not dev.synchronized:
            raise NeighborError("Neighbor device {} not synchronized".format(hostname))
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
        except Exception as e:
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
            raise DeviceStateException("Device must be in state INIT to continue init step 2")
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
    with open('/etc/cnaas-nms/repository.yml', 'r') as db_file:
        repo_config = yaml.safe_load(db_file)
        local_repo_path = repo_config['templates_local']
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
