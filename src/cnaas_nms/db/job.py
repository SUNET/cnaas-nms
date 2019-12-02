import enum
import datetime
import json
from typing import Optional

from sqlalchemy import Column, Integer, Unicode
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


class JobStatus(enum.Enum):
    UNKNOWN = 0
    SCHEDULED = 1
    RUNNING = 2
    FINISHED = 3
    EXCEPTION = 4

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
    status = Column(Enum(JobStatus), default=JobStatus.SCHEDULED)
    scheduled_time = Column(DateTime, default=datetime.datetime.utcnow)
    start_time = Column(DateTime)
    finish_time = Column(DateTime)
    function_name = Column(Unicode(255))
    scheduled_by = Column(Unicode(255))
    comment = Column(Unicode(255))
    ticket_ref = Column(Unicode(32))
    next_job_id = Column(Integer, ForeignKey('job.id'))
    next_job = relationship("Job", remote_side=[id])
    result = Column(JSONB)
    exception = Column(JSONB)
    finished_devices = Column(JSONB)

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
                print("DEBUG01: {}".format(type(value)))
                value = json.loads(value)
            d[col.name] = value
        return d

    def start_job(self, function_name: str):
        self.function_name = function_name
        self.start_time = datetime.datetime.utcnow()
        self.status = JobStatus.RUNNING
        self.finished_devices = []

    def finish_success(self, res: dict, next_job_id: Optional[int]):
        try:
            if isinstance(res, NornirJobResult) and isinstance(res.nrresult, AggregatedResult):
                self.result = nr_result_serialize(res.nrresult)
                self.result['_totals'] = {'selected_devices': len(res.nrresult)}
                if res.change_score:
                    self.result['_totals']['change_score'] = res.change_score
            elif isinstance(res, (StrJobResult, DictJobResult)):
                self.result = res.result
            else:
                self.result = json.dumps(res, default=json_dumper)
        except Exception as e:
            logger.warning("Job {} got unserializable result after finishing: {}". \
                           format(self.id, self.result))
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
