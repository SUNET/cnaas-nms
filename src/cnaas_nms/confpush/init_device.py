from nornir import InitNornir

from nornir.core.deserializer.inventory import Inventory
from nornir.core.filter import F
from nornir.core.task import MultiResult

from nornir.plugins.tasks import networking, text
from nornir.plugins.functions.text import print_title, print_result

import cnaas_nms.confpush.nornir_helper
from cnaas_nms.cmdb.session import sqla_session
from cnaas_nms.cmdb.device import Device, DeviceState, DeviceStateException
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.confpush.nornir_helper import NornirJobResult

import datetime

def push_base_management(task):
    template_vars = {
        'uplinks': [{'ifname': 'Ethernet2'}],
        'mgmt_vlan_id': 600,
        'mgmt_ip': '10.0.6.10/24',
        'mgmt_gw': '10.0.6.1'
    }
    print("DEBUG1: "+task.host.name)
    #TODO: find uplinks automatically
    #TODO: check compatability, same dist pair and same ports on dists
    #TODO: query mgmt vlan, ip, gw for dist pair

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
             dry_run=True # TODO: temp for testing
             )

@job_wrapper
def init_access_device_step1(hostname: str) -> NornirJobResult:
    """Initialize access device for management by CNaaS-NMS

    Args:
        hostname (str): Hostname of device to initialize

    Returns:
        Nornir result object

    Raises:
        DeviceStateException
    """
    with sqla_session() as session:
        dev = session.query(Device).filter(Device.hostname == hostname).one()
        if dev.state != DeviceState.DISCOVERED:
            raise DeviceStateException("Device must be in state DISCOVERED to begin init")
        #TODO: more checks?
        dev.state = DeviceState.INIT

    # step2. push management config
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)

    nrresult = nr_filtered.run(task=push_base_management)

    print_result(nrresult)
    # expect connection lost

    # step3. register apscheduler job that continues steps

    scheduler = Scheduler()
    next_job = scheduler.add_onetime_job(
        init_access_device_step2,
        when=1,
        kwargs={'hostname':hostname})

    print(f"Step 2 scheduled as ID {next_job.id}")
    #TODO: trigger more jobs later with more delays? cancel if first succeeds

    return NornirJobResult(
        nrresult = nrresult,
        next_job_id = next_job.id
    )

@job_wrapper
def init_access_device_step2(hostname: str, iteration:int=-1):
    # step4+ in apjob: if success, update management ip and device state, trigger external stuff?
    print(f"step2: { hostname }")
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)

    nrresult = nr_filtered.run(task=networking.napalm_get, getters=["facts"])

    if nrresult.failed:
        # schedule new job unless iter is over max
        return NornirJobResult(
            nrresult = nrresult,
        #    next_job_id = next_job.id
        )
    
    try:
        facts = nrresult[hostname][0].result['facts']
        found_hostname = facts['hostname']
    except:
        raise #TODO: define exception types
    print(f"Check match {hostname} = {found_hostname}")

    return NornirJobResult(
        nrresult = nrresult
    )
