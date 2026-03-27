import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func

from cnaas_nms.api.dependencies import get_current_user
from cnaas_nms.api.filtering import build_filter, pagination_headers
from cnaas_nms.api.response import CnaasJSONResponse, empty_result
from cnaas_nms.db.job import Job, JobStatus
from cnaas_nms.db.joblock import Joblock
from cnaas_nms.db.session import sqla_session
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.tools.log import get_logger

router = APIRouter(tags=["jobs"])


class JobAction(BaseModel):
    action: str
    abort_reason: Optional[str] = None


class JoblockDelete(BaseModel):
    name: str


def filter_job_dict(job_dict: dict, args: dict) -> dict:
    """Filter out parts of job result dict based on query string arguments."""
    logger = get_logger()
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
        for filter_item in sorted(filter_items, reverse=True):
            for hostname, value in job_dict["result"]["devices"].items():
                try:
                    del job_dict["result"]["devices"][hostname]["job_tasks"][filter_item]
                except KeyError:
                    pass
                except Exception as e:
                    logger.debug("job filter_response exception: {}".format(e))
    return job_dict


@router.get("/jobs")
def get_jobs(request: Request, user: str = Depends(get_current_user)):
    """Get one or more jobs."""
    data: dict[str, Any] = {"jobs": []}
    total_count = 0
    args = dict(request.query_params)

    per_page = int(args.get("per_page", 50))
    page = int(args.get("page", 1))

    with sqla_session() as session:
        query = session.query(Job, func.count(Job.id).over().label("total"))
        try:
            query = build_filter(Job, query, args, per_page=per_page, page=page)
        except Exception as e:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data="Unable to filter jobs: {}".format(e)),
            )
        for instance in query:
            job_dict = instance.Job.as_dict()
            filtered_job_dict = filter_job_dict(job_dict, args)
            data["jobs"].append(filtered_job_dict)
            total_count = instance.total

    headers = pagination_headers(
        total_count, args, per_page=per_page, page=page, base_url=str(request.base_url) + "api/v1.0/jobs"
    )
    return CnaasJSONResponse(
        content=empty_result(status="success", data=data),
        headers=headers,
    )


@router.get("/job/{job_id}")
def get_job_by_id(job_id: int, request: Request, user: str = Depends(get_current_user)):
    """Get job information by ID."""
    args = dict(request.query_params)
    with sqla_session() as session:
        job = session.query(Job).filter(Job.id == job_id).one_or_none()
        if job:
            job_dict = job.as_dict()
            filtered_job_dict = filter_job_dict(job_dict, args)
            return empty_result(data={"jobs": [filtered_job_dict]})
        else:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data="No job with id {} found".format(job_id)),
            )


@router.put("/job/{job_id}")
def modify_job(job_id: int, job_action: JobAction, user: str = Depends(get_current_user)):
    """Modify a job (e.g. abort)."""
    with sqla_session() as session:
        job = session.query(Job).filter(Job.id == job_id).one_or_none()
        if not job:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data="No job with id {} found".format(job_id)),
            )
        job_status = job.status

    action = str(job_action.action).upper()
    if action == "ABORT":
        allowed_jobstates = [JobStatus.SCHEDULED, JobStatus.RUNNING]
        if job_status not in allowed_jobstates:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(
                    status="error",
                    data="Job id {} is in state {}, must be {} to abort".format(
                        job_id, job_status, (" or ".join([x.name for x in allowed_jobstates]))
                    ),
                ),
            )
        abort_reason = "Aborted via API call"
        if job_action.abort_reason and isinstance(job_action.abort_reason, str):
            abort_reason = job_action.abort_reason[:255]

        abort_reason += " (aborted by {})".format(user)

        if job_status == JobStatus.SCHEDULED:
            scheduler = Scheduler()
            scheduler.remove_scheduled_job(job_id=job_id, abort_message=abort_reason)
            time.sleep(2)
        elif job_status == JobStatus.RUNNING:
            with sqla_session() as session:
                job = session.query(Job).filter(Job.id == job_id).one_or_none()
                if not job:
                    return CnaasJSONResponse(
                        status_code=400,
                        content=empty_result(status="error", data="No job with id {} found".format(job_id)),
                    )
                job.status = JobStatus.ABORTING

        with sqla_session() as session:
            job = session.query(Job).filter(Job.id == job_id).one_or_none()
            if not job:
                return CnaasJSONResponse(
                    status_code=400,
                    content=empty_result(status="error", data="No job with id {} found".format(job_id)),
                )
            return empty_result(data={"jobs": [job.as_dict()]})
    else:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="Unknown action: {}".format(action)),
        )


@router.get("/joblocks")
def get_joblocks(user: str = Depends(get_current_user)):
    """Get job locks."""
    locks = []
    with sqla_session() as session:
        for lock in session.query(Joblock).all():
            locks.append(lock.as_dict())
    return empty_result("success", data={"locks": locks})


@router.delete("/joblocks")
def delete_joblock(joblock_delete: JoblockDelete, user: str = Depends(get_current_user)):
    """Remove a job lock."""
    with sqla_session() as session:
        lock = session.query(Joblock).filter(Joblock.name == joblock_delete.name).one_or_none()
        if lock:
            session.delete(lock)
        else:
            return CnaasJSONResponse(
                status_code=404,
                content=empty_result("error", "No such lock found in database"),
            )

    return empty_result("success", data={"name": joblock_delete.name, "status": "deleted"})
