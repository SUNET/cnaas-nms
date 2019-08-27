#from __future__ import annotations
# this future import seems to break enum translation on DataclassPersistance class
import bson.json_util
import datetime
import enum
from dataclasses import dataclass
from typing import Optional, Union, List

from nornir.core.task import AggregatedResult

from cnaas_nms.confpush.nornir_helper import nr_result_serialize, NornirJobResult
from cnaas_nms.scheduler.jobresult import StrJobResult, DictJobResult
from cnaas_nms.db.dataclass_persistence import DataclassPersistence
from cnaas_nms.tools.log import get_logger

logger = get_logger()

class JobStatus(enum.Enum):
    UNKNOWN = 0
    SCHEDULED = 1
    RUNNING = 2
    FINISHED = 3
    EXCEPTION = 4

@dataclass
class Jobtracker(DataclassPersistence):
    start_time: Optional[datetime.datetime] = None
    finish_time: Optional[datetime.datetime] = None
    status: JobStatus = JobStatus.UNKNOWN
    function_name: Optional[str] = None
    result: Optional[Union[str, dict]] = None
    exception: Optional[str] = None
    traceback: Optional[str] = None
    next_job_id: Optional[str] = None
    finished_devices: Optional[list] = None

    def start(self, fname: str):
        self.update({
            'start_time': datetime.datetime.utcnow(),
            'function_name': fname,
            'status': JobStatus.RUNNING,
            'finished_devices': ['kaka']
        })

    def finish_success(self, res: dict, next_job_id: Optional[str]):
        try:
            if isinstance(res, NornirJobResult) and isinstance(res.nrresult, AggregatedResult):
                self.result = nr_result_serialize(res.nrresult)
                self.result['_totals'] = {'selected_devices': len(res.nrresult)}
                if res.change_score:
                    self.result['_totals']['change_score'] = res.change_score
            elif isinstance(res, (StrJobResult, DictJobResult)):
                self.result = res.result
            else:
                self.result = bson.json_util.dumps(res)
        except Exception as e:
            logger.warning("Job {} got unserializable result after finishing: {}".\
                           format(self.id, self.result))
            self.result = 'unserializable'
        self.update({
            'finish_time': datetime.datetime.utcnow(),
            'status': JobStatus.FINISHED,
            'result': self.result,
            'next_job_id': next_job_id
        })

    def finish_exception(self, e: Exception, traceback: str):
        logger.warning("Job {} finished with exception {}".format(self.id, str(e)))
        self.update({
            'finish_time': datetime.datetime.utcnow(),
            'status': JobStatus.EXCEPTION,
            'exception': bson.json_util.dumps({'type': type(e).__name__, 'args': e.args}),
            'traceback': bson.json_util.dumps(traceback)
        })

    def finished_devices_update(self, host):
        finished_devices = self.finished_devices
        finished_devices.append(host)
        self.update({'finished_devices': finished_devices})

    @classmethod
    def get_running_jobs(cls, start_time: Optional[datetime.datetime] = None) -> List:
        if not start_time:
            start_time = datetime.datetime.utcnow() - datetime.timedelta(minutes = 15)
        ret = []
        last_jobs = cls.get_last_entries()
        for job_data in last_jobs:
            job: Jobtracker = Jobtracker()
            job.from_dict(job_data)
            if not job.start_time:
                continue
            if job.status == JobStatus.RUNNING and job.start_time > start_time:
                ret.append(job)
        return ret
