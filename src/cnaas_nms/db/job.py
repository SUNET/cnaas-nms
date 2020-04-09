import enum
import datetime
import json
from typing import Optional, Dict

from sqlalchemy import Column, Integer, Unicode, SmallInteger
from sqlalchemy import Enum, DateTime
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql.json import JSONB
from sqlalchemy.orm import relationship
from nornir.core.task import AggregatedResult

import cnaas_nms.db.base
import cnaas_nms.db.device
from cnaas_nms.confpush.nornir_helper import nr_result_serialize, NornirJobResult
from cnaas_nms.scheduler.jobresult import StrJobResult, DictJobResult
from cnaas_nms.db.helper import json_dumper
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

    @classmethod
    def has_value(cls, value):
        return any(value == item.value for item in cls)

    @classmethod
    def has_name(cls, value):
        return any(value == item.name for item in cls)


class Job(cnaas_nms.db.base.Base):
    __tablename__ = 'job'
    __table_args__ = (
        None,
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    status = Column(Enum(JobStatus), index=True, default=JobStatus.SCHEDULED)
    scheduled_time = Column(DateTime, default=datetime.datetime.utcnow)
    start_time = Column(DateTime)
    finish_time = Column(DateTime, index=True)
    function_name = Column(Unicode(255))
    scheduled_by = Column(Unicode(255))
    comment = Column(Unicode(255))
    ticket_ref = Column(Unicode(32), index=True)
    next_job_id = Column(Integer, ForeignKey('job.id'))
    next_job = relationship("Job", remote_side=[id])
    result = Column(JSONB)
    exception = Column(JSONB)
    finished_devices = Column(JSONB)
    change_score = Column(SmallInteger)  # should be in range 0-100

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

    def start_job(self, function_name: str, scheduled_by: str):
        self.function_name = function_name
        self.start_time = datetime.datetime.utcnow()
        self.status = JobStatus.RUNNING
        self.finished_devices = []
        self.scheduled_by = scheduled_by

    def finish_success(self, res: dict, next_job_id: Optional[int]):
        try:
            if isinstance(res, NornirJobResult) and isinstance(res.nrresult, AggregatedResult):
                self.result = {'devices': nr_result_serialize(res.nrresult)}
                if res.change_score and type(res.change_score) == int:
                    self.change_score = res.change_score
            elif isinstance(res, (StrJobResult, DictJobResult)):
                self.result = res.result
            else:
                self.result = json.dumps(res, default=json_dumper)
        except Exception as e:
            logger.exception("Job {} got unserializable ({}) result after finishing: {}". \
                           format(self.id, str(e), self.result))
            self.result = {"error": "unserializable"}

        self.finish_time = datetime.datetime.utcnow()
        self.status = JobStatus.FINISHED
        if next_job_id:
            # TODO: check if this exists in the db?
            self.next_job_id = next_job_id

    def finish_exception(self, e: Exception, traceback: str):
        logger.warning("Job {} finished with exception: {}".format(self.id, str(e)))
        self.finish_time = datetime.datetime.utcnow()
        self.status = JobStatus.EXCEPTION
        try:
            self.exception = json.dumps(
                {
                    'message': str(e),
                    'type': type(e).__name__,
                    'args': e.args,
                    'traceback': traceback
                }, default=json_dumper)
        except Exception as e:
            errmsg = "Unable to serialize exception or traceback: {}".format(str(e))
            logger.exception(errmsg)
            self.exception = {"error": errmsg}

    def finish_abort(self, message: str):
        logger.debug("Job {} aborted: {}".format(self.id, message))
        self.finish_time = datetime.datetime.utcnow()
        self.status = JobStatus.ABORTED
        self.result = {"message": message}


    @classmethod
    def clear_jobs(cls, session):
        """Clear/release all locks in the database."""
        running_jobs = session.query(Job).filter(Job.status == JobStatus.RUNNING).all()
        job: Job
        for job in running_jobs:
            logger.warning(
                "Job found in unfinished RUNNING state at startup moved to ABORTED, id: {}".
                format(job.id))
            job.status = JobStatus.ABORTED

        scheduled_jobs = session.query(Job).filter(Job.status == JobStatus.SCHEDULED).all()
        job: Job
        for job in scheduled_jobs:
            # Clear jobs that should have been run in the past, timing might need tuning if
            # APschedulers misfire_grace_time is modified
            aps_misfire_grace_time = datetime.timedelta(seconds=1)
            if job.scheduled_time < (datetime.datetime.utcnow() - aps_misfire_grace_time):
                logger.warning(
                    "Job found in past SCHEDULED state at startup moved to ABORTED, id: {}".
                    format(job.id))
                job.status = JobStatus.ABORTED

    @classmethod
    def get_previous_config(cls, session, hostname: str, previous: Optional[int] = None,
                            job_id: Optional[int] = None,
                            before: Optional[datetime.datetime] = None) -> Dict[str, str]:
        """

        Args:
            session:
            hostname:
            previous:
            job_id:
            before:

        Returns:
            Returns a result dict with keys: config, job_id and finish_time

        """
        result = {}
        query_part = session.query(Job).filter(Job.function_name == 'sync_devices'). \
            filter(Job.result.has_key('devices')).filter(Job.result['devices'].has_key(hostname))

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

        result['job_id'] = job.id
        result['finish_time'] = job.finish_time.isoformat()

        if 'job_tasks' not in job.result['devices'][hostname]:
            raise InvalidJobError("Invalid job data found in database: missing job_tasks")

        for task in job.result['devices'][hostname]['job_tasks']:
            if task['task_name'] == 'Generate device config':
                result['config'] = task['result']

        return result
