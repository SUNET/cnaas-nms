
import bson.json_util
import json
from flask import request
from flask_restful import Resource

from cnaas_nms.api.generic import limit_results, empty_result
from cnaas_nms.scheduler.jobtracker import Jobtracker


class JobsApi(Resource):
    def get(self):
        ret_jobs = []
        for job in Jobtracker.get_last_entries(num_entries=limit_results()):
            jt = Jobtracker()
            jt.from_dict(job)
            ret_jobs.append(jt.to_dict(json_serializable=True))
        result = empty_result(data={'jobs': ret_jobs})
        return result
