from bson.objectid import ObjectId
import bson.json_util
import datetime

from cnaas_nms.cmdb.session import mongo_db
from cnaas_nms.confpush.nornir_helper import nr_result_serialize, NornirJobResult
from cnaas_nms.scheduler.jobresult import StrJobResult, DictJobResult
from nornir.core.task import AggregatedResult

from dataclasses import dataclass
from typing import Optional, Union

@dataclass
class Jobtracker(object):
    id: Optional[ObjectId] = None
    start_time: Optional[datetime.datetime] = None
    finish_time: Optional[datetime.datetime] = None
    status: Optional[str] = None
    result: Optional[Union[str, dict]] = None
    exception: Optional[str] = None
    traceback: Optional[str] = None

    def from_dict(self, in_dict):
        for key in self.__dataclass_fields__.keys():
            if key == 'id':
                self.__setattr__('id', in_dict['_id'])
            else:
                if key in in_dict:
                    self.__setattr__(key, in_dict[key])

    def to_dict(self, json_serializable=False):
        ret = {}
        for key in self.__dataclass_fields__.keys():
            field = self.__getattribute__(key)
            if json_serializable:
                ret[key] = self.serialize(field)
            else:
                ret[key] = field
        return ret

    @classmethod
    def serialize(cls, property):
        if isinstance(property, (type(None), str, int)):
            return property
        elif isinstance(property, (ObjectId, datetime.datetime)):
            return str(property)
        elif isinstance(property, dict):
            return property #TODO: recurse?

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
            self.from_dict(data)

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
            elif isinstance(res, (StrJobResult, DictJobResult)):
                self.result = res.result
            else:
                self.result = bson.json_util.dumps(res)
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
