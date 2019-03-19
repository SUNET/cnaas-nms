from typing import Optional
import datetime

from ipaddress import IPv4Interface
from nornir import InitNornir

from nornir.core.deserializer.inventory import Inventory
from nornir.core.filter import F
from nornir.core.task import MultiResult

from nornir.plugins.tasks import networking, text
from nornir.plugins.functions.text import print_title, print_result
from apscheduler.job import Job

import cnaas_nms.confpush.nornir_helper
import cnaas_nms.confpush.get
import cnaas_nms.cmdb.helper
from cnaas_nms.cmdb.session import sqla_session
from cnaas_nms.cmdb.device import Device, DeviceState, DeviceType, DeviceStateException
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.confpush.nornir_helper import NornirJobResult


class ConnectionCheckError(Exception):
    pass

def push_base_management(task, device_variables):
    template_vars = {
        'uplinks': device_variables['uplinks'],
        'mgmt_vlan_id': device_variables['mgmt_vlan_id'],
        'mgmt_ip': str(device_variables['mgmt_ipif']),
        'mgmt_gw': device_variables['mgmt_gw']
    }

    r = task.run(task=text.template_file,
                 name="Base management",
                 template="managed-base.j2",
                 path=f"../templates/{task.host.platform}",
                 **template_vars)

    #TODO: Handle template not found, variables not defined

    task.host["config"] = r.result

    task.run(task=networking.napalm_configure,
             name="Push base management config",
             replace=False,
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
        print("DEBUG100: uplinks: {} neighbor_hostnames: {}".format(uplinks, neighbor_hostnames))
        #TODO: check compatability, same dist pair and same ports on dists
        mgmtdomain = cnaas_nms.cmdb.helper.find_mgmtdomain(session, neighbor_hostnames) 
        if not mgmtdomain:
            raise Exception(
                "Could not find appropriate management domain for uplink peer devices: {}".format(
                neighbor_hostnames))
        mgmt_ip = mgmtdomain.find_free_mgmt_ip(session)
        if not mgmt_ip:
            raise Exception("Could not find free management IP for management domain {}".format(
            mgmtdomain.id))
        mgmt_gw_ipif = IPv4Interface(mgmtdomain.ipv4_gw)
        device_variables = {
            'mgmt_ipif': IPv4Interface('{}/{}'.format(mgmt_ip, mgmt_gw_ipif.network.prefixlen)),
            'uplinks': uplinks,
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
        nrresult = nr_filtered.run(task=push_base_management, device_variables=device_variables)
    except Exception as e:
        pass # ignore exception, we expect to loose connectivity.
             # sometimes we get no exception here, but it's saved in result
             # other times we get socket.timeout, pyeapi.eapilib.ConnectionError or
             # napalm.base.exceptions.ConnectionException to handle here?
    if not nrresult.failed:
        raise #we don't expect success here

    print_result(nrresult)

    with sqla_session() as session:
        dev = session.query(Device).filter(Device.id == device_id).one()
        dev.management_ip = device_variables['mgmt_ipif'].ip

    # step3. register apscheduler job that continues steps

    scheduler = Scheduler()
    next_job = scheduler.add_onetime_job(
        'cnaas_nms.confpush.init_device:init_access_device_step2',
        when=0,
        kwargs={'device_id':device_id, 'iteration': 1})

    print(f"Step 2 scheduled as ID {next_job.id}")
    #TODO: trigger more jobs later with more delays? cancel if first succeeds

    return NornirJobResult(
        nrresult = nrresult,
        next_job_id = next_job.id
    )

def schedule_init_access_device_step2(device_id: int, iteration: int) -> Optional[Job]:
    max_iterations = 2
    if iteration > 0 and iteration < max_iterations:
        scheduler = Scheduler()
        next_job = scheduler.add_onetime_job(
            'cnaas_nms.confpush.init_device:init_access_device_step2',
            when=(30*iteration),
            kwargs={'device_id':device_id, 'iteration': iteration+1})
        return next_job
    else:
        return None

@job_wrapper
def init_access_device_step2(device_id: int, iteration:int=-1) -> NornirJobResult:
    # step4+ in apjob: if success, update management ip and device state, trigger external stuff?
    print(f"step2: { device_id }")
    with sqla_session() as session:
        dev = session.query(Device).filter(Device.id == device_id).one()
        if dev.state != DeviceState.INIT:
            raise DeviceStateException("Device must be in state INIT to continue init step 2")
        hostname = dev.hostname
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)

    nrresult = nr_filtered.run(task=networking.napalm_get, getters=["facts"])

    if nrresult.failed:
        next_job = schedule_init_access_device_step2(device_id, iteration)
        if next_job:
            return NornirJobResult(
                nrresult = nrresult,
                next_job_id = next_job.id
            )
        else:
            return NornirJobResult(nrresult = nrresult)
    try:
        facts = nrresult[hostname][0].result['facts']
        found_hostname = facts['hostname']
    except:
        raise #TODO: define exception types
    print(f"Check match {hostname} = {found_hostname}")
    if hostname != found_hostname:
        raise #TODO: define exception types

    with sqla_session() as session:
        dev = session.query(Device).filter(Device.id == device_id).one()
        dev.state = DeviceState.MANAGED
        dev.device_type = DeviceType.ACCESS
        #TODO: remove dhcp_ip ?

    return NornirJobResult(
        nrresult = nrresult
    )
