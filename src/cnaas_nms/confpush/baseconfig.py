
from typing import Optional

from nornir.core.filter import F
from nornir.plugins.tasks import networking, text

from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.confpush.nornir_helper import NornirJobResult
from cnaas_nms.cmdb.device import DeviceType

def push_basetemplate(task):
    template_vars = {
        'uplinks': [{'ifname': 'Ethernet2'}],
        'mgmt_vlan_id': 600,
        'mgmt_ip': '10.0.6.10/24',
        'mgmt_gw': '10.0.6.1'
    }
    print("DEBUG1: "+task.host.name)

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
def sync_basetemplate(hostname: Optional[str]=None,
                      device_type: Optional[DeviceType]=None,
                      dry_run: bool=True) -> NornirJobResult:
    """Synchronize base system template to device or device group.

    Args:
        hostname: Hostname of a single device to sync
        device_type: A device group type to sync
        dry_run: Set to true to only perform a NAPALM dry_run of config changes 
    """
    nrresult = None

    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    if hostname and isinstance(hostname, str):
        nr_filtered = nr.filter(name=hostname)
    elif device_type and isinstance(device_type, DeviceType):
        group_name = ('T_'+device_type.value)
        nr_filtered = nr.filter(F(groups__contains=group_name))
    else:
        raise ValueError("hostname or device_type must be specified")

    nrresult = nr_filtered.run(task=push_basetemplate)

    return NornirJobResult(
        nrresult = nrresult
    )
