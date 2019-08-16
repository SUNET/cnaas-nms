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
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.confpush.nornir_helper import NornirJobResult
from cnaas_nms.confpush.update import update_interfacedb
from cnaas_nms.db.git import RepoStructureException
from cnaas_nms.db.settings import get_settings
from cnaas_nms.plugins.pluginmanager import PluginManagerHandler
from cnaas_nms.tools.log import get_logger

logger = get_logger()


class ConnectionCheckError(Exception):
    pass


class InitError(Exception):
    pass


def push_base_management_access(task, device_variables):
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
    # Merge dicts
    template_vars = {**device_variables, **settings}

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


@job_wrapper
def init_access_device_step1(device_id: int, new_hostname: str) -> NornirJobResult:
    """Initialize access device for management by CNaaS-NMS

    Args:
        hostname (str): Hostname of device to initialize

    Returns:
        Nornir result object

    Raises:
        DeviceStateException
    """
    # Check that we can find device and that it's in the correct state to start init
    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.id == device_id).one()
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
        raise ConnectionCheckError(f"Failed to connect to device_id {device_id}")

    cnaas_nms.confpush.get.update_linknets(old_hostname)
    uplinks = []
    neighbor_hostnames = []
    with sqla_session() as session:
        dev = session.query(Device).filter(Device.hostname == old_hostname).one()
        for neighbor_d in dev.get_neighbors(session):
            if neighbor_d.device_type == DeviceType.DIST:
                local_if = dev.get_link_to_local_ifname(session, neighbor_d)
                if local_if:
                    uplinks.append({'ifname': local_if})
                    neighbor_hostnames.append(neighbor_d.hostname)
        logger.debug("Uplinks for device {} detected: {} neighbor_hostnames: {}".\
                     format(device_id, uplinks, neighbor_hostnames))
        #TODO: check compatability, same dist pair and same ports on dists
        mgmtdomain = cnaas_nms.db.helper.find_mgmtdomain(session, neighbor_hostnames)
        if not mgmtdomain:
            raise Exception(
                "Could not find appropriate management domain for uplink peer devices: {}".format(
                    neighbor_hostnames))
        # TODO: save ip in temporary table so it's not allocated to someone else while pushing config
        mgmt_ip = mgmtdomain.find_free_mgmt_ip(session)
        if not mgmt_ip:
            raise Exception("Could not find free management IP for management domain {}".format(
            mgmtdomain.id))
        mgmt_gw_ipif = IPv4Interface(mgmtdomain.ipv4_gw)
        device_variables = {
            'mgmt_ipif': str(IPv4Interface('{}/{}'.format(mgmt_ip, mgmt_gw_ipif.network.prefixlen))),
            'mgmt_ip': str(mgmt_ip),
            'mgmt_prefixlen': int(mgmt_gw_ipif.network.prefixlen),
            'uplinks': uplinks,
            'access_auto': [],
            'mgmt_vlan_id': mgmtdomain.vlan,
            'mgmt_gw': mgmt_gw_ipif.ip
        }
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
                                   device_variables=device_variables)
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

    print_result(nrresult)

    with sqla_session() as session:
        dev = session.query(Device).filter(Device.id == device_id).one()
        dev.management_ip = device_variables['mgmt_ip']

    # Plugin hook, allocated IP
    # send: mgmt_ip , mgmt_network , hostname , VRF?
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
        kwargs={'device_id':device_id, 'iteration': 1})

    logger.debug(f"Step 2 scheduled as ID {next_job_id}")

    return NornirJobResult(
        nrresult = nrresult,
        next_job_id = next_job_id
    )


def schedule_init_access_device_step2(device_id: int, iteration: int) -> Optional[Job]:
    max_iterations = 2
    if iteration > 0 and iteration < max_iterations:
        scheduler = Scheduler()
        next_job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.init_device:init_access_device_step2',
            when=(30*iteration),
            kwargs={'device_id':device_id, 'iteration': iteration+1})
        return next_job_id
    else:
        return None


@job_wrapper
def init_access_device_step2(device_id: int, iteration:int=-1) -> NornirJobResult:
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
        next_job_id = schedule_init_access_device_step2(device_id, iteration)
        if next_job_id:
            return NornirJobResult(
                nrresult = nrresult,
                next_job_id = next_job_id
            )
        else:
            return NornirJobResult(nrresult = nrresult)
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
        #TODO: remove dhcp_ip ?

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

    try:
        update_interfacedb(hostname, replace=True)
    except Exception as e:
        logger.exception(
            "Exception while updating interface database for device {}: {}".\
            format(hostname, str(e)))

    return NornirJobResult(
        nrresult = nrresult
    )
