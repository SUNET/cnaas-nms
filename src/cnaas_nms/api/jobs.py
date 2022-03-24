import json
import time

from flask import make_response, request
from flask_restx import Namespace, Resource, fields
from sqlalchemy import func

from cnaas_nms.api.generic import build_filter, empty_result, pagination_headers
from cnaas_nms.db.job import Job, JobStatus
from cnaas_nms.db.joblock import Joblock
from cnaas_nms.db.session import sqla_session
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.security import get_jwt_identity, jwt_required
from cnaas_nms.version import __api_version__

job_api = Namespace("job", description="API for handling jobs", prefix="/api/{}".format(__api_version__))

jobs_api = Namespace("jobs", description="API for handling jobs", prefix="/api/{}".format(__api_version__))

joblock_api = Namespace("joblocks", description="API for handling jobs", prefix="/api/{}".format(__api_version__))

job_model = job_api.model("jobs", {"name": fields.String(required=True)})


def filter_job_dict(job_dict: dict, args: dict) -> dict:
    """Filter out parts of job result dict based on query string arguments."""
    logger = get_logger()
    # Define order of nornir tasks in known types of jobs
    filter_map = {"syncto": {"config": 1, "diff": 2}}
    filter_items = []
    if (
        not isinstance(job_dict, dict)
        or "result" not in job_dict
        or not isinstance(job_dict["result"], dict)
        or "devices" not in job_dict["result"]
        or "function_name" not in job_dict
        or not isinstance(job_dict["function_name"], str)
    ):
        return job_dict

    if job_dict["function_name"].startswith("sync_devices"):
        for arg, value in args.items():
            if arg == "filter_jobresult" and isinstance(value, str):
                for item in value.split(","):
                    if item in filter_map["syncto"].keys():
                        filter_items.append(filter_map["syncto"][item])
        # Remove items starting from the end of the list so indexes don't change
        for filter_item in sorted(filter_items, reverse=True):
            for hostname, _ in job_dict["result"]["devices"].items():
                try:
                    del job_dict["result"]["devices"][hostname]["job_tasks"][filter_item]
                except KeyError:
                    pass
                except Exception as e:
                    logger.debug("job filter_response exception: {}".format(e))
    return job_dict


class JobsApi(Resource):
    @jwt_required
    def get(self):
        """Get one or more jobs."""
        data = {"jobs": []}
        total_count = 0
        args = request.args
        with sqla_session() as session:
            query = session.query(Job, func.count(Job.id).over().label("total"))
            try:
                query = build_filter(Job, query)
            except Exception as e:
                return empty_result(status="error", data="Unable to filter jobs: {}".format(e)), 400
            for instance in query:
                job_dict = instance.Job.as_dict()
                filtered_job_dict = filter_job_dict(job_dict, args)
                data["jobs"].append(filtered_job_dict)
                total_count = instance.total

        resp = make_response(json.dumps(empty_result(status="success", data=data)), 200)
        resp.headers["Content-Type"] = "application/json"
        resp.headers = {**resp.headers, **pagination_headers(total_count)}
        return resp


class JobByIdApi(Resource):
    @jwt_required
    def get(self, job_id):
        """Get job information by ID."""
        args = request.args
        with sqla_session() as session:
            job = session.query(Job).filter(Job.id == job_id).one_or_none()
            if job:
                job_dict = job.as_dict()
                filtered_job_dict = filter_job_dict(job_dict, args)
                return empty_result(data={"jobs": [filtered_job_dict]})
            else:
                return empty_result(status="error", data="No job with id {} found".format(job_id)), 400

    @jwt_required
    def put(self, job_id):
        json_data = request.get_json()
        if "action" not in json_data:
            return empty_result(status="error", data="Action must be specified"), 400

        with sqla_session() as session:
            job = session.query(Job).filter(Job.id == job_id).one_or_none()
            if not job:
                return empty_result(status="error", data="No job with id {} found".format(job_id)), 400
            job_status = job.status

        action = str(json_data["action"]).upper()
        if action == "ABORT":
            allowed_jobstates = [JobStatus.SCHEDULED, JobStatus.RUNNING]
            if job_status not in allowed_jobstates:
                return (
                    empty_result(
                        status="error",
                        data="Job id {} is in state {}, must be {} to abort".format(
                            job_id, job_status, (" or ".join([x.name for x in allowed_jobstates]))
                        ),
                    ),
                    400,
                )
            abort_reason = "Aborted via API call"
            if "abort_reason" in json_data and isinstance(json_data["abort_reason"], str):
                abort_reason = json_data["abort_reason"][:255]

            abort_reason += " (aborted by {})".format(get_jwt_identity())

            if job_status == JobStatus.SCHEDULED:
                scheduler = Scheduler()
                scheduler.remove_scheduled_job(job_id=job_id, abort_message=abort_reason)
                time.sleep(2)
            elif job_status == JobStatus.RUNNING:
                with sqla_session() as session:
                    job = session.query(Job).filter(Job.id == job_id).one_or_none()
                    job.status = JobStatus.ABORTING

            with sqla_session() as session:
                job = session.query(Job).filter(Job.id == job_id).one_or_none()
                return empty_result(data={"jobs": [job.as_dict()]})
        else:
            return empty_result(status="error", data="Unknown action: {}".format(action)), 400


class JobLockApi(Resource):
    @jwt_required
    def get(self):
        """Get job locks."""
        locks = []
        with sqla_session() as session:
            for lock in session.query(Joblock).all():
                locks.append(lock.as_dict())
        return empty_result("success", data={"locks": locks})

    @jwt_required
    @job_api.expect(job_model)
    def delete(self):
        """Remove job locks."""
        json_data = request.get_json()
        if "name" not in json_data or not json_data["name"]:
            return empty_result("error", "No lock name specified"), 400

        with sqla_session() as session:
            lock = session.query(Joblock).filter(Joblock.name == json_data["name"]).one_or_none()
            if lock:
                session.delete(lock)
            else:
                return empty_result("error", "No such lock found in database"), 404

        return empty_result("success", data={"name": json_data["name"], "status": "deleted"})


jobs_api.add_resource(JobsApi, "")
job_api.add_resource(JobByIdApi, "/<int:job_id>")
joblock_api.add_resource(JobLockApi, "")
