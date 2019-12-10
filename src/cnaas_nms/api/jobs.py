import json
from flask import request, make_response
from flask_restplus import Resource, Namespace, fields
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from cnaas_nms.api.generic import empty_result, build_filter
from cnaas_nms.db.job import Job
from cnaas_nms.db.joblock import Joblock
from cnaas_nms.db.session import sqla_session
from cnaas_nms.version import __api_version__


job_api = Namespace('job', description='API for handling jobs',
                    prefix='/api/{}'.format(__api_version__))

jobs_api = Namespace('jobs', description='API for handling jobs',
                     prefix='/api/{}'.format(__api_version__))

joblock_api = Namespace('joblocks', description='API for handling jobs',
                        prefix='/api/{}'.format(__api_version__))

job_model = job_api.model('jobs', {'name': fields.String(required=True)})


class JobsApi(Resource):
    @jwt_required
    def get(self):
        """ Get one or more jobs """
        data = {'jobs': []}
        total_count = 0
        with sqla_session() as session:
            query = session.query(Job, func.count(Job.id).over().label('total')).order_by(Job.id)
            query = build_filter(Job, query)
            for instance in query:
                data['jobs'].append(instance.Job.as_dict())
                total_count = instance.total

        resp = make_response(json.dumps(empty_result(status='success', data=data)), 200)
        resp.headers['X-Total-Count'] = total_count
        return resp


class JobByIdApi(Resource):
    @jwt_required
    def get(self, job_id):
        """ Get job information by ID """
        with sqla_session() as session:
            job = session.query(Job).filter(Job.id == job_id).one_or_none()
            if job:
                return empty_result(data={'jobs': [job.as_dict()]})
            else:
                return empty_result(status='error', data="No job with id {} found".format(job_id)), 400


class JobLockApi(Resource):
    @jwt_required
    def get(self):
        """ Get job locks """
        locks = []
        with sqla_session() as session:
            for lock in session.query(Joblock).all():
                locks.append(lock.as_dict())
        return empty_result('success', data={'locks': locks})

    @jwt_required
    @job_api.expect(job_model)
    def delete(self):
        """ Remove job locks """
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


jobs_api.add_resource(JobsApi, '')
job_api.add_resource(JobByIdApi, '/<int:job_id>')
joblock_api.add_resource(JobLockApi, '')
