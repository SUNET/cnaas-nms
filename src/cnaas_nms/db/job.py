import datetime
import enum
import json
from typing import Dict, Optional

from nornir.core.task import AggregatedResult
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, SmallInteger, Unicode
from sqlalchemy.dialects.postgresql.json import JSONB
from sqlalchemy.orm import relationship

import cnaas_nms.db.base
import cnaas_nms.db.device
from cnaas_nms.confpush.nornir_helper import NornirJobResult, nr_result_serialize
from cnaas_nms.db.helper import json_dumper
from cnaas_nms.scheduler.jobresult import DictJobResult, StrJobResult
from cnaas_nms.tools.event import add_event
from cnaas_nms.tools.log import get_logger

logger = get_logger()


class JobNotFoundError(Exception):
    pass


class InvalidJobError(Exception):
    pass


class JobStatus(enum.Enum):
    UNKNOWN = 0
    SCHEDULED = 1
    RUNNING = 2
    FINISHED = 3
    EXCEPTION = 4
    ABORTED = 5
    ABORTING = 6

    @classmethod
    def has_value(cls, value):
        return any(value == item.value for item in cls)

    @classmethod
    def has_name(cls, value):
        return any(value == item.name for item in cls)


class Job(cnaas_nms.db.base.Base):
    __tablename__ = "job"
    __table_args__ = (None,)
    id = Column(Integer, autoincrement=True, primary_key=True)
    status = Column(Enum(JobStatus), index=True, default=JobStatus.SCHEDULED)
    scheduled_time = Column(DateTime, default=datetime.datetime.utcnow)
    start_time = Column(DateTime)
    finish_time = Column(DateTime, index=True)
    function_name = Column(Unicode(255))
    scheduled_by = Column(Unicode(255))
    comment = Column(Unicode(255))
    ticket_ref = Column(Unicode(32), index=True)
    next_job_id = Column(Integer, ForeignKey("job.id"))
    next_job = relationship("Job", remote_side=[id])
    result = Column(JSONB)
    exception = Column(JSONB)
    finished_devices = Column(JSONB)
    change_score = Column(SmallInteger)  # should be in range 0-100
    start_arguments = Column(JSONB)

    def as_dict(self) -> dict:
        """Return JSON serializable dict."""
        d = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if issubclass(value.__class__, enum.Enum):
                value = value.name
            elif issubclass(value.__class__, cnaas_nms.db.base.Base):
                continue
            elif issubclass(value.__class__, datetime.datetime):
                value = json_dumper(value)
            elif type(col.type) == JSONB and value and type(value) == str:
                value = json.loads(value)
            d[col.name] = value
        return d

    def start_job(self, function_name: Optional[str] = None, scheduled_by: Optional[str] = None):
        self.start_time = datetime.datetime.utcnow()
        self.status = JobStatus.RUNNING
        self.finished_devices = []
        if function_name:
            self.function_name = function_name
        if scheduled_by:
            self.scheduled_by = scheduled_by
        try:
            json_data = json.dumps(
                {
                    "job_id": self.id,
                    "status": "RUNNING",
                    "function_name": self.function_name,
                    "scheduled_by": self.scheduled_by,
                }
            )
            add_event(json_data=json_data, event_type="update", update_type="job")
        except Exception:  # noqa: S110
            pass

    def finish_success(self, res: dict, next_job_id: Optional[int]):
        try:
            if isinstance(res, NornirJobResult) and isinstance(res.nrresult, AggregatedResult):
                self.result = {"devices": nr_result_serialize(res.nrresult)}
                if res.change_score and type(res.change_score) == int:
                    self.change_score = res.change_score
            elif isinstance(res, (StrJobResult, DictJobResult)):
                self.result = res.result
            else:
                self.result = json.dumps(res, default=json_dumper)
        except Exception as e:
            logger.exception(
                "Job {} got unserializable ({}) result after finishing: {}".format(self.id, str(e), self.result)
            )
            self.result = {"error": "unserializable"}

        self.finish_time = datetime.datetime.utcnow()
        if self.status == JobStatus.ABORTING:
            self.status = JobStatus.ABORTED
        else:
            self.status = JobStatus.FINISHED
        if next_job_id:
            # TODO: check if this exists in the db?
            self.next_job_id = next_job_id
        try:
            event_data = {"job_id": self.id, "status": self.status.name}
            if next_job_id:
                event_data["next_job_id"] = next_job_id
            json_data = json.dumps(event_data)
            add_event(json_data=json_data, event_type="update", update_type="job")
        except Exception:  # noqa: S110
            pass

    def finish_exception(self, e: Exception, traceback: str):
        logger.warning("Job {} finished with exception: {}".format(self.id, str(e)))
        self.finish_time = datetime.datetime.utcnow()
        self.status = JobStatus.EXCEPTION
        try:
            self.exception = json.dumps(
                {"message": str(e), "type": type(e).__name__, "args": e.args, "traceback": traceback},
                default=json_dumper,
            )
        except Exception as e:
            errmsg = "Unable to serialize exception or traceback: {}".format(str(e))
            logger.exception(errmsg)
            self.exception = {"error": errmsg}
        try:
            json_data = json.dumps(
                {
                    "job_id": self.id,
                    "status": "EXCEPTION",
                    "exception": str(e),
                }
            )
            add_event(json_data=json_data, event_type="update", update_type="job")
        except Exception:  # noqa: S110
            pass

    def finish_abort(self, message: str):
        logger.debug("Job {} aborted: {}".format(self.id, message))
        self.finish_time = datetime.datetime.utcnow()
        self.status = JobStatus.ABORTED
        self.result = {"message": message}
        try:
            json_data = json.dumps(
                {
                    "job_id": self.id,
                    "status": "ABORTED",
                    "message": message,
                }
            )
            add_event(json_data=json_data, event_type="update", update_type="job")
        except Exception:  # noqa: S110
            pass

    @classmethod
    def clear_jobs(cls, session):
        """Clear/release all locks in the database."""
        running_jobs = session.query(Job).filter(Job.status == JobStatus.RUNNING).all()
        job: Job
        for job in running_jobs:
            logger.warning("Job found in unfinished RUNNING state at startup moved to ABORTED, id: {}".format(job.id))
            job.status = JobStatus.ABORTED

        aborting_jobs = session.query(Job).filter(Job.status == JobStatus.ABORTING).all()
        job: Job
        for job in aborting_jobs:
            logger.warning("Job found in unfinished ABORTING state at startup moved to ABORTED, id: {}".format(job.id))
            job.status = JobStatus.ABORTED

        scheduled_jobs = session.query(Job).filter(Job.status == JobStatus.SCHEDULED).all()
        job: Job
        for job in scheduled_jobs:
            # Clear jobs that should have been run in the past, timing might need tuning if
            # APschedulers misfire_grace_time is modified
            aps_misfire_grace_time = datetime.timedelta(seconds=1)
            if job.scheduled_time < (datetime.datetime.utcnow() - aps_misfire_grace_time):
                logger.warning("Job found in past SCHEDULED state at startup moved to ABORTED, id: {}".format(job.id))
                job.status = JobStatus.ABORTED

    @classmethod
    def get_previous_config(
        cls,
        session,
        hostname: str,
        previous: Optional[int] = None,
        job_id: Optional[int] = None,
        before: Optional[datetime.datetime] = None,
    ) -> Dict[str, str]:
        """Get full configuration for a device from a previous job.

        Args:
            session: sqla_session
            hostname: hostname of device to get config for
            previous: number of revisions back to get config from
            job_id: specific job to get config from
            before: date to get config before

        Returns:
            Returns a result dict with keys: config, job_id and finish_time
        """
        result = {}
        query_part = (
            session.query(Job)
            .filter(Job.function_name == "sync_devices")
            .filter(Job.result.has_key("devices"))  # noqa: W601 TODO: fix deprecation
            .filter(Job.result["devices"].has_key(hostname))
        )

        if job_id and type(job_id) == int:
            query_part = query_part.filter(Job.id == job_id)
        elif previous and type(previous) == int:
            query_part = query_part.order_by(Job.id.desc()).offset(previous)
        elif before and type(before) == datetime.datetime:
            query_part = query_part.filter(Job.finish_time < before).order_by(Job.id.desc())
        else:
            query_part = query_part.order_by(Job.id.desc())

        job: Job = query_part.first()
        if not job:
            raise JobNotFoundError("No matching job found")

        result["job_id"] = job.id
        result["finish_time"] = job.finish_time.isoformat(timespec="seconds")

        if "job_tasks" not in job.result["devices"][hostname] or "failed" not in job.result["devices"][hostname]:
            raise InvalidJobError("Invalid job data found in database: missing job_tasks")

        for task in job.result["devices"][hostname]["job_tasks"]:
            if task["task_name"] == "Generate device config":
                result["config"] = task["result"]

        result["failed"] = job.result["devices"][hostname]["failed"]

        return result

    @classmethod
    def check_job_abort_status(cls, session, job_id) -> bool:
        """Check if specified job is being aborted."""
        job = session.query(Job).filter(Job.id == job_id).one_or_none()
        if not job:
            return True
        if job.status != JobStatus.RUNNING:
            return True
        return False
