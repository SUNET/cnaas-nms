from flask import request
from flask_restful import Resource

from cnaas_nms.api.generic import limit_results, empty_result
from cnaas_nms.scheduler.jobtracker import Jobtracker
from cnaas_nms.db.joblock import Joblock
from cnaas_nms.db.session import sqla_session


class JobsApi(Resource):
    def get(self):
        ret_jobs = []
        for job in Jobtracker.get_last_entries(num_entries=limit_results()):
            jt = Jobtracker()
            jt.from_dict(job)
            ret_jobs.append(jt.to_dict(json_serializable=True))
        result = empty_result(data={'jobs': ret_jobs})
        return result


class JobByIdApi(Resource):
    def get(self, id):
        job = Jobtracker()
        try:
            job.load(id)
        except Exception as e:
            return empty_result(status='error', data=str(e)), 400
        result = empty_result(data={'jobs': [job.to_dict(json_serializable=True)]})
        return result


class JobLockApi(Resource):
    def get(self):
        locks = []
        with sqla_session() as session:
            for lock in session.query(Joblock).all():
                locks.append(lock.as_dict())
        return empty_result('success', data={'locks': locks})

    def delete(self):
        json_data = request.get_json()

        if 'name' not in json_data or not json_data['name']:
            return empty_result('error', "No lock name specified"), 400

        with sqla_session() as session:
            lock = session.query(Joblock).filter(Joblock.name == json_data['name']).one_or_none()
            if lock:
                session.delete(lock)
            else:
                return empty_result('error', "No such lock found in database"), 404

        return empty_result('success', data={'name': json_data['name'], 'status': 'deleted'})


