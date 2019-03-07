from nornir import InitNornir

from nornir.core.deserializer.inventory import Inventory
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

#(Pdb) res.nrresult.items()
#dict_items([('mac-080027F60C55', MultiResult: [Result: "push_base_management", Result: "Base management", Result: "Push base management config"])])

def nr_result_serialize(result: AggregatedResult):
    if not isinstance(result, AggregatedResult):
        raise ValueError("result must be of type AggregatedResult")

    hosts = {}    
    for host, multires in result.items():
        print("host: {} {}".format(host, multires))
        hosts[host] = []
        for res in multires:
            print("result: {}".format(res.result))
            print("result: {}".format(res.diff))
            print("result: {}".format(res.failed))
            hosts[host].append({
                'result': res.result,
                'diff': res.diff,
                'failed': res.failed
            })
    return hosts
