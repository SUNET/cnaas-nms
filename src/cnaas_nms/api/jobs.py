
import bson.json_util
import json
from flask import request
from flask_restful import Resource

from cnaas_nms.cmdb.session import mongo_db
from cnaas_nms.api.generic import limit_results, empty_result
from cnaas_nms.scheduler.jobtracker import Jobtracker


class JobsApi(Resource):
    def get(self):
        ret_jobs = []
        with mongo_db() as db:
            jobs = db['jobs']
            data = jobs.find().sort('_id', -1).limit(limit_results())
            for job in data:
                jt = Jobtracker()
                jt.from_dict(job)
                ret_jobs.append(jt.to_dict(json_serializable=True))
        result = empty_result(data={'jobs': ret_jobs})
        return result
