from typing import Optional
from ipaddress import IPv4Interface

from nornir.plugins.tasks import networking, text
from nornir.plugins.functions.text import print_result
from nornir.core.inventory import ConnectionOptions
from napalm.base.exceptions import SessionLockedException
from apscheduler.job import Job
import yaml
import os

import cnaas_nms.confpush.nornir_helper
import cnaas_nms.confpush.get
import cnaas_nms.db.helper
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import Device, DeviceState, DeviceType, DeviceStateException
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.confpush.nornir_helper import NornirJobResult
from cnaas_nms.confpush.update import update_interfacedb_worker
from cnaas_nms.confpush.sync_devices import get_mlag_vars
from cnaas_nms.db.git import RepoStructureException
from cnaas_nms.db.settings import get_settings
from cnaas_nms.plugins.pluginmanager import PluginManagerHandler
from cnaas_nms.db.reservedip import ReservedIP
from cnaas_nms.tools.log import get_logger
from cnaas_nms.scheduler.thread_data import set_thread_data


class ConnectionCheckError(Exception):
    pass


class InitError(Exception):
    pass


def push_base_management_access(task, device_variables, job_id):
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
        template = mapping['ACCESS']['entrypoint']

    settings, settings_origin = get_settings(task.host.name, DeviceType.ACCESS)

    # Add all environment variables starting with TEMPLATE_SECRET_ to
    # the list of configuration variables. The idea is to store secret
    # configuration outside of the templates repository.
    template_secrets = {}
    for env in os.environ:
        if env.startswith('TEMPLATE_SECRET_'):
            template_secrets[env] = os.environ[env]

    # Merge dicts, this will overwrite interface list from settings
    template_vars = {**settings, **device_variables, **template_secrets}

    r = task.run(task=text.template_file,
                 name="Generate initial device config",
                 template=template,
                 path=f"{local_repo_path}/{task.host.platform}",
                 **template_vars)

    #TODO: Handle template not found, variables not defined

    task.host["config"] = r.result
    # Use extra low timeout for this since we expect to loose connectivity after changing IP
    task.host.connection_options["napalm"] = ConnectionOptions(extras={"timeout": 5})

    task.run(task=networking.napalm_configure,
             name="Push base management config",
             replace=True,
             configuration=task.host["config"],
             dry_run=False # TODO: temp for testing
             )


def pre_init_checks(session, device_id) -> Device:
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
        nrresult_old = nr_old_filtered.run(task=networking.napalm_get, getters=["facts"])
    except Exception as e:
        raise ConnectionCheckError(f"Failed to connect to device_id {device_id}: {str(e)}")
    if nrresult_old.failed:
        print_result(nrresult_old)
        raise ConnectionCheckError(f"Failed to connect to device_id {device_id}")
    return dev


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


@job_wrapper
def init_access_device_step1(device_id: int, new_hostname: str,
                             mlag_peer_id: Optional[int] = None,
                             mlag_peer_new_hostname: Optional[str] = None,
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

        cnaas_nms.confpush.get.update_linknets(session, dev.hostname)  # update linknets using LLDP data
        uplink_hostnames = dev.get_uplink_peer_hostnames(session)

        if mlag_peer_id and mlag_peer_new_hostname:
            mlag_peer_dev = pre_init_checks(session, mlag_peer_id)
            cnaas_nms.confpush.get.update_linknets(session, mlag_peer_dev.hostname)
            update_interfacedb_worker(session, dev, replace=True, delete=False,
                                      mlag_peer_hostname=mlag_peer_dev.hostname)
            uplink_hostnames.append(mlag_peer_dev.get_uplink_peer_hostnames(session))
            # check that both devices see the correct MLAG peer
            pre_init_check_mlag(session, dev, mlag_peer_dev)
            pre_init_check_mlag(session, mlag_peer_dev, dev)
        elif mlag_peer_id or mlag_peer_new_hostname:
            raise ValueError("mlag_peer_id and mlag_peer_new_hostname must be specified together")
        else:
            update_interfacedb_worker(session, dev, replace=True, delete=False)

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
        device_variables = {
            'mgmt_ipif': str(IPv4Interface('{}/{}'.format(mgmt_ip, mgmt_gw_ipif.network.prefixlen))),
            'mgmt_ip': str(mgmt_ip),
            'mgmt_prefixlen': int(mgmt_gw_ipif.network.prefixlen),
            'interfaces': [],
            'mgmt_vlan_id': mgmtdomain.vlan,
            'mgmt_gw': mgmt_gw_ipif.ip
        }
        intfs = session.query(Interface).filter(Interface.device == dev).all()
        intf: Interface
        for intf in intfs:
            intfdata = None
            if intf.data:
                intfdata = dict(intf.data)
            device_variables['interfaces'].append({
                'name': intf.name,
                'ifclass': intf.configtype.name,
                'data': intfdata
            })
        mlag_vars = get_mlag_vars(session, dev)
        device_variables = {**device_variables, **mlag_vars}
        # Update device state
        dev = session.query(Device).filter(Device.id == device_id).one()
        dev.state = DeviceState.INIT
        dev.hostname = new_hostname
        session.commit()
        hostname = dev.hostname

    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)

    # step2. push management config
    try:
        nrresult = nr_filtered.run(task=push_base_management_access,
                                   device_variables=device_variables,
                                   job_id=job_id)
    except SessionLockedException as e:
        # TODO: Handle this somehow?
        pass
    except Exception as e:
        # Ignore exception, we expect to loose connectivity.
        # Sometimes we get no exception here, but it's saved in result
        # other times we get socket.timeout, pyeapi.eapilib.ConnectionError or
        # napalm.base.exceptions.ConnectionException to handle here?
        pass
    if not nrresult.failed:
        raise Exception  # we don't expect success here

    with sqla_session() as session:
        dev = session.query(Device).filter(Device.id == device_id).one()
        dev.management_ip = device_variables['mgmt_ip']
        # Remove the reserved IP since it's now saved in the device database instead
        reserved_ip = session.query(ReservedIP).filter(ReservedIP.device == dev).one_or_none()
        if reserved_ip:
            session.delete(reserved_ip)

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
    scheduler = Scheduler()
    next_job_id = scheduler.add_onetime_job(
        'cnaas_nms.confpush.init_device:init_access_device_step2',
        when=0,
        scheduled_by=scheduled_by,
        kwargs={'device_id': device_id, 'iteration': 1})

    logger.debug(f"Step 2 scheduled as ID {next_job_id}")

    return NornirJobResult(
        nrresult=nrresult,
        next_job_id=next_job_id
    )


def schedule_init_access_device_step2(device_id: int, iteration: int,
                                      scheduled_by: str) -> Optional[Job]:
    max_iterations = 2
    if iteration > 0 and iteration < max_iterations:
        scheduler = Scheduler()
        next_job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.init_device:init_access_device_step2',
            when=(30*iteration),
            scheduled_by=scheduled_by,
            kwargs={'device_id': device_id, 'iteration': iteration+1})
        return next_job_id
    else:
        return None


@job_wrapper
def init_access_device_step2(device_id: int, iteration: int = -1,
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
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)

    nrresult = nr_filtered.run(task=networking.napalm_get, getters=["facts"])

    if nrresult.failed:
        next_job_id = schedule_init_access_device_step2(device_id, iteration,
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
        found_hostname = facts['hostname']
    except:
        raise InitError("Could not log in to device during init step 2")
    if hostname != found_hostname:
        raise InitError("Newly initialized device presents wrong hostname")

    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.id == device_id).one()
        dev.state = DeviceState.MANAGED
        dev.device_type = DeviceType.ACCESS
        dev.synchronized = False
        dev.serial = facts['serial_number']
        dev.vendor = facts['vendor']
        dev.model = facts['model']
        dev.os_version = facts['os_version']
        management_ip = dev.management_ip
        dev.dhcp_ip = None

    # Plugin hook: new managed device
    # Send: hostname , device type , serial , platform , vendor , model , os version
    try:
        pmh = PluginManagerHandler()
        pmh.pm.hook.new_managed_device(
            hostname=hostname,
            device_type=DeviceType.ACCESS.name,
            serial_number=facts['serial_number'],
            vendor=facts['vendor'],
            model=facts['model'],
            os_version=facts['os_version'],
            management_ip=str(management_ip)
        )
    except Exception as e:
        logger.exception("Error while running plugin hooks for new_managed_device: ".format(str(e)))

    return NornirJobResult(
        nrresult = nrresult
    )


def schedule_discover_device(ztp_mac: str, dhcp_ip: str, iteration: int,
                             scheduled_by: str) -> Optional[Job]:
    max_iterations = 5
    if iteration > 0 and iteration < max_iterations:
        scheduler = Scheduler()
        next_job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.init_device:discover_device',
            when=(60*iteration),
            scheduled_by=scheduled_by,
            kwargs={'ztp_mac': ztp_mac, 'dhcp_ip': dhcp_ip,
                    'iteration': iteration+1})
        return next_job_id
    else:
        return None


def set_hostname_task(task, new_hostname: str):
    with open('/etc/cnaas-nms/repository.yml', 'r') as db_file:
        repo_config = yaml.safe_load(db_file)
        local_repo_path = repo_config['templates_local']
    template_vars = {
        'hostname': new_hostname
    }
    task.run(
        task=text.template_file,
        name="Configure hostname",
        template="hostname.j2",
        path=f"{local_repo_path}/{task.host.platform}",
        **template_vars
    )


@job_wrapper
def discover_device(ztp_mac: str, dhcp_ip: str, iteration=-1,
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

    nrresult = nr_filtered.run(task=networking.napalm_get, getters=["facts"])

    if nrresult.failed:
        logger.info("Could not contact device with ztp_mac {} (attempt {})".format(
            ztp_mac, iteration
        ))
        next_job_id = schedule_discover_device(ztp_mac, dhcp_ip, iteration,
                                               scheduled_by)
        if next_job_id:
            return NornirJobResult(
                nrresult = nrresult,
                next_job_id = next_job_id
            )
        else:
            return NornirJobResult(nrresult = nrresult)
    try:
        facts = nrresult[hostname][0].result['facts']
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.ztp_mac == ztp_mac).one()
            dev.serial = facts['serial_number']
            dev.vendor = facts['vendor']
            dev.model = facts['model']
            dev.os_version = facts['os_version']
            dev.state = DeviceState.DISCOVERED
            new_hostname = dev.hostname
            logger.info(f"Device with ztp_mac {ztp_mac} successfully scanned, " +
                        "moving to DISCOVERED state")
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
