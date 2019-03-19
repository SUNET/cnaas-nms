from nornir import InitNornir

from nornir.core.task import AggregatedResult, MultiResult, Result
from cnaas_nms.scheduler.jobresult import JobResult

from dataclasses import dataclass
from typing import Optional


@dataclass
class NornirJobResult(JobResult):
    nrresult: Optional[MultiResult] = None


def cnaas_init():
    nr = InitNornir(
        inventory={
            "plugin": "cnaas_nms.confpush.nornir_plugins.cnaas_inventory.CnaasInventory"
        }
    )
    return nr


def nr_result_serialize(result: AggregatedResult):
    if not isinstance(result, AggregatedResult):
        raise ValueError("result must be of type AggregatedResult")

    hosts = {}    
    for host, multires in result.items():
        hosts[host] = []
        for res in multires:
            hosts[host].append({
                'name': res.name,
                'result': res.result,
                'diff': res.diff,
                'failed': res.failed
            })
    return hosts
