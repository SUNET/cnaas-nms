
from typing import Optional

from nornir.core.filter import F
from nornir.plugins.tasks import networking, text

from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.confpush.nornir_helper import NornirJobResult
from cnaas_nms.db.device import DeviceType
from cnaas_nms.tools.log import get_logger

logger = get_logger()


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
