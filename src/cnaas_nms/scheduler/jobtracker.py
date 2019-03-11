import bson.json_util
import datetime

from cnaas_nms.confpush.nornir_helper import nr_result_serialize, NornirJobResult
from cnaas_nms.scheduler.jobresult import StrJobResult, DictJobResult
from cnaas_nms.cmdb.dataclass_persistence import DataclassPersistence
from nornir.core.task import AggregatedResult

from dataclasses import dataclass
from typing import Optional, Union

@dataclass
class Jobtracker(DataclassPersistence):
    start_time: Optional[datetime.datetime] = None
    finish_time: Optional[datetime.datetime] = None
    status: Optional[str] = None
    function_name: Optional[str] = None
    result: Optional[Union[str, dict]] = None
    exception: Optional[str] = None
    traceback: Optional[str] = None
    next_job_id: Optional[str] = None

    def start(self, fname: str):
        self.update({
            'start_time': datetime.datetime.utcnow(),
            'function_name': fname,
            'status': 'running'
        })

    def finish_success(self, res: dict, next_job_id: Optional[str]):
        try:
            if isinstance(res, NornirJobResult) and isinstance(res.nrresult, AggregatedResult):
                self.result = nr_result_serialize(res.nrresult)
            elif isinstance(res, (StrJobResult, DictJobResult)):
                self.result = res.result
            else:
                self.result = bson.json_util.dumps(res)
        except Exception as e:
            self.result = 'unserializable'
        self.update({
            'finish_time': datetime.datetime.utcnow(),
            'status': 'finished',
            'result': self.result,
            'next_job_id': next_job_id
        })

    def finish_exception(self, e: Exception, traceback: str):
        self.update({
            'finish_time': datetime.datetime.utcnow(),
            'status': 'exception',
            'exception': bson.json_util.dumps({'type': type(e).__name__, 'args': e.args}),
            'traceback': bson.json_util.dumps(traceback)
        })
