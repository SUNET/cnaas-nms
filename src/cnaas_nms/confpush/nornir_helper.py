from dataclasses import dataclass
from typing import Optional, Tuple, List, Union
import os

from nornir import InitNornir
from nornir.core import Nornir
from nornir.core.task import AggregatedResult, MultiResult
from nornir.core.filter import F
from nornir.core.plugins.inventory import InventoryPluginRegister
from jinja2 import Environment as JinjaEnvironment

from cnaas_nms.confpush.nornir_plugins.cnaas_inventory import CnaasInventory
from cnaas_nms.scheduler.jobresult import JobResult
from cnaas_nms.tools import jinja_filters


@dataclass
class NornirJobResult(JobResult):
    nrresult: Optional[MultiResult] = None
    change_score: Optional[float] = None


cnaas_jinja_env = JinjaEnvironment(
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True)

cnaas_jinja_env.filters['increment_ip'] = jinja_filters.increment_ip


def cnaas_init() -> Nornir:
    InventoryPluginRegister.register("CnaasInventory", CnaasInventory)
    nr = InitNornir(
        runner={
            "plugin": "threaded",
            "options": {
                "num_workers": 50
            }
        },
        inventory={
            "plugin": "CnaasInventory"
        },
        logging={"log_file": "/tmp/nornir-pid{}.log".format(os.getpid()), "level": "DEBUG"}
    )
    return nr


def nr_result_serialize(result: AggregatedResult):
    if not isinstance(result, AggregatedResult):
        raise ValueError("result must be of type AggregatedResult")

    hosts = {}    
    for host, multires in result.items():
        hosts[host] = {'failed': False, 'job_tasks': []}
        for res in multires:
            hosts[host]['job_tasks'].append({
                'task_name': res.name,
                'result': res.result,
                'diff': res.diff,
                'failed': res.failed
            })
            if res.failed:
                hosts[host]['failed'] = True
    return hosts


def inventory_selector(nr: Nornir, resync: bool = True,
                       hostname: Optional[Union[str, List[str]]] = None,
                       device_type: Optional[str] = None,
                       group: Optional[str] = None) -> Tuple[Nornir, int, List[str]]:
    """Return a filtered Nornir inventory with only the selected devices

    Args:
        nr: Nornir object
        resync: Set to false if you want to filter out devices that are synchronized
        hostname: Select device by hostname (string) or list of hostnames (list)
        device_type: Select device by device_type (string)
        group: Select device by group (string)

    Returns:
        Tuple with: filtered Nornir inventory, total device count selected,
                    list of hostnames that was skipped because of resync=False
    """
    skipped_devices = []
    if hostname:
        if isinstance(hostname, str):
            nr_filtered = nr.filter(name=hostname).filter(managed=True)
        elif isinstance(hostname, list):
            nr_filtered = nr.filter(filter_func=lambda h: h.name in hostname).filter(managed=True)
        else:
            raise ValueError("Can't select hostname based on type {}".type(hostname))
    elif device_type:
        nr_filtered = nr.filter(F(groups__contains='T_'+device_type)).filter(managed=True)
    elif group:
        nr_filtered = nr.filter(F(groups__contains=group)).filter(managed=True)
    else:
        # all devices
        nr_filtered = nr.filter(managed=True)

    if resync or hostname:
        return nr_filtered, len(nr_filtered.inventory.hosts), skipped_devices
    else:
        pre_device_list = list(nr_filtered.inventory.hosts.keys())
        nr_filtered = nr_filtered.filter(synchronized=False)
        post_device_list = list(nr_filtered.inventory.hosts.keys())
        skipped_devices = [x for x in pre_device_list if x not in post_device_list]
        return nr_filtered, len(post_device_list), skipped_devices
