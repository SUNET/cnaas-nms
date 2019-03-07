from bson.objectid import ObjectId
import bson.json_util
import datetime

from cnaas_nms.cmdb.session import mongo_db
from cnaas_nms.confpush.nornir_helper import nr_result_serialize, NornirJobResult
from cnaas_nms.scheduler.jobresult import StrJobResult
from nornir.core.task import AggregatedResult

from typing import Optional

class Jobtracker(object):
    def __init__(self):
        self.id = ''
        self.start_time = None
        self.finish_time = None
        self.status = 'unknown'
        self.result = None
        self.exception = None
        self.traceback = None

    def create(self):
        with mongo_db() as db:
            jobs = db['jobs']
            self.status = 'scheduled'
            self.id = jobs.insert_one({'status':self.status}).inserted_id
            return str(self.id)

    def load(self, id):
        with mongo_db() as db:
            jobs = db['jobs']
            data = jobs.find_one({'_id': ObjectId(id)})
            self.id = data['_id']
            if 'start_time' in data:
                self.start_time = data['start_time']
            #TODO: load other stuff
            #self.finish_time = data['finish_time']
            self.status = data['status']

    def start(self, fname: str):
        self.start_time = datetime.datetime.utcnow()
        self.status = 'running'
        with mongo_db() as db:
            jobs = db['jobs']
            jobs.update_one(
                {'_id': self.id},
                {
                    "$set":
                    {
                        'start_time': self.start_time,
                        'function_name': fname,
                        'status': self.status
                    }
                }
            )

    def finish_success(self, res: dict, next_job_id: Optional[str]):
        self.finish_time = datetime.datetime.utcnow()
        try:
            if isinstance(res, NornirJobResult) and isinstance(res.nrresult, AggregatedResult):
                self.result = nr_result_serialize(res.nrresult)
            elif isinstance(res, StrJobResult):
                self.result = res.result
            else:
                self.result = res
            self.result = bson.json_util.dumps(self.result)
        except Exception as e:
            self.result = 'unserializable'
        self.status = 'finished'
        with mongo_db() as db:
            jobs = db['jobs']
            jobs.update_one(
                {'_id': self.id},
                {
                    "$set":
                    {
                        'finish_time': self.finish_time,
                        'status': self.status,
                        'result': self.result,
                        'next_job_id': next_job_id
                    }
                }
            )

    def finish_exception(self, e: Exception, traceback: str):
        self.finish_time = datetime.datetime.utcnow()
        self.exception = bson.json_util.dumps({'type': type(e).__name__, 'args': e.args})
        self.traceback = bson.json_util.dumps(traceback)
        self.status = 'exception'
        with mongo_db() as db:
            jobs = db['jobs']
            jobs.update_one(
                {'_id': self.id},
                {
                    "$set":
                    {
                        'finish_time': self.finish_time,
                        'status': self.status,
                        'exception': self.exception,
                        'traceback': self.traceback
                    }
                }
            )
