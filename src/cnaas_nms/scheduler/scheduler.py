import inspect
import datetime
import fcntl
import os
import json
from pytz import utc
from typing import Optional, Union
from types import FunctionType

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from cnaas_nms.db.session import sqla_session, get_sqlalchemy_conn_str
from cnaas_nms.db.job import Job, JobStatus
from cnaas_nms.tools.log import get_logger

logger = get_logger()


class SingletonType(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonType, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Scheduler(object, metaclass=SingletonType):
    def __init__(self):
        threads = 10
        self.is_mule = False
        # If scheduler is already started, use uwsgi ipc to send job to mule process
        self.lock_f = open('/tmp/scheduler.lock', 'w')
        try:
            fcntl.lockf(self.lock_f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            try:
                import uwsgi
            except Exception:
                self.use_mule = False
            else:
                self.use_mule = True
        else:
            self.use_mule = False
        caller = self.get_caller(caller=inspect.currentframe())
        if caller == 'api':
            sqlalchemy_url = get_sqlalchemy_conn_str()
            self._scheduler = BackgroundScheduler(
                executors={'default': ThreadPoolExecutor(threads)},
                jobstores={'default': SQLAlchemyJobStore(url=sqlalchemy_url)},
                job_defaults={},
                timezone=utc
            )
            logger.info("Scheduler started with persistent jobstore, {} threads".format(threads))
        elif caller == 'mule':
            sqlalchemy_url = get_sqlalchemy_conn_str()
            self._scheduler = BackgroundScheduler(
                executors={'default': ThreadPoolExecutor(threads)},
                jobstores={'default': SQLAlchemyJobStore(url=sqlalchemy_url)},
                job_defaults={},
                timezone=utc
            )
            logger.info("Scheduler started with persistent jobstore, {} threads".format(threads))
            self.is_mule = True
        elif self.use_mule:
            logger.info("Use uwsgi to send jobs to mule process".format(threads))
            self._scheduler = None
        else:
            self._scheduler = BackgroundScheduler(
                executors={'default': ThreadPoolExecutor(threads)},
                jobstores={'default': MemoryJobStore()},
                job_defaults={},
                timezone=utc
            )
            logger.info("Scheduler started with in-memory jobstore, {} threads".format(threads))

    def __del__(self):
        if self.lock_f:
            fcntl.lockf(self.lock_f, fcntl.LOCK_UN)
            self.lock_f.close()
            os.unlink('/tmp/scheduler.lock')

    def get_scheduler(self):
        return self._scheduler

    def get_caller(self, caller):
        """Check if API main run was the caller."""
        frameinfo = inspect.getframeinfo(caller.f_back.f_back)
        filename = '/'.join(frameinfo.filename.split('/')[-2:])
        function = frameinfo.function
        if filename == 'cnaas_nms/run.py' and function == 'get_app':
            logger.info("Scheduler started from filename {} function {} (API mode)".format(
                filename, function))
            return 'api'
        elif filename == 'cnaas_nms/scheduler_mule.py':
            logger.info("Scheduler started from filename {} function {} (uwsgi mule mode)".format(
                filename, function))
            return 'mule'
        else:
            logger.info("Scheduler started from filename {} function {} (Standalone mode)".format(
                filename, function))
            return 'other'

    def start(self):
        if self._scheduler and not self.use_mule:
            return self._scheduler.start()

    def shutdown(self):
        if self._scheduler and not self.use_mule:
            return self._scheduler.shutdown()

    def add_local_job(self, func, **kwargs):
        """Add job to local scheduler."""
        return self._scheduler.add_job(func, **kwargs)

    def remove_local_job(self, job_id):
        """Remove job from local scheduler."""
        return self._scheduler.remove_job(str(job_id))

    def remove_scheduled_job(self, job_id, abort_message="removed"):
        """Remove scheduled job from mule worker or local scheduler depending
        on setup."""
        if self.use_mule:
            try:
                import uwsgi
            except Exception as e:
                logger.exception("use_mule is set but not running in uwsgi")
                raise e
            args = {
                "scheduler_action": "remove",
                "id": str(job_id)
            }
            uwsgi.mule_msg(json.dumps(args))
        else:
            self.remove_local_job(job_id)

        with sqla_session() as session:
            job = session.query(Job).filter(Job.id == job_id).one_or_none()
            job.finish_abort(message=abort_message)

    def add_onetime_job(self, func: Union[str, FunctionType],
                        when: Optional[int] = None,
                        scheduled_by: Optional[str] = None, **kwargs) -> int:
        """Schedule a job to run at a later time on the mule worker or
        local scheduler depending on setup.

        Some extra checks against kwargs are performed here. If kwarg
        with name 'dry_run' is included, (dry_run) is appended to function
        name. If kwarg job_comment or job_ticket_ref are included, those
        fields in the job will be populated.

        Args:
            func: The function to call
            when: Optional number of seconds to wait before starting job
            scheduled_by: Username that scheduled the job
            **kwargs: Arguments to pass through to called function
        Returns:
            int: job_id
        """
        if when and isinstance(when, int):
            trigger = 'date'
            run_date = datetime.datetime.utcnow() + datetime.timedelta(seconds=when)
        else:
            trigger = None
            run_date = None

        if isinstance(func, FunctionType):
            func_qualname = str(func.__qualname__)
        else:
            func_qualname = str(func)
        func_name = func_qualname.split(':')[-1]

        # Append (dry_run) to function name if set, so we can distinguish dry_run jobs
        try:
            if kwargs['dry_run']:
                func_name += " (dry_run)"
        except Exception:
            pass

        with sqla_session() as session:
            job = Job()
            if run_date:
                job.scheduled_time = run_date
            job.function_name = func_name
            if scheduled_by is None:
                scheduled_by = 'unknown'
            job.scheduled_by = scheduled_by
            job_comment = kwargs.pop('job_comment', None)
            if job_comment and isinstance(job_comment, str):
                job.comment = job_comment[:255]
            job_ticket_ref = kwargs.pop('job_ticket_ref', None)
            if job_ticket_ref and isinstance(job_comment, str):
                job.ticket_ref = job_ticket_ref[:32]
            session.add(job)
            session.flush()
            job_id = job.id

        kwargs['job_id'] = job_id
        kwargs['scheduled_by'] = scheduled_by
        if self.use_mule:
            try:
                import uwsgi
            except Exception as e:
                logger.exception("use_mule is set but not running in uwsgi")
                raise e
            args = dict(kwargs)
            args['func'] = func_qualname
            args['trigger'] = trigger
            args['when'] = when
            args['id'] = str(job_id)
            uwsgi.mule_msg(json.dumps(args))
            return job_id
        else:
            self.add_local_job(func, trigger=trigger, kwargs=kwargs, id=str(job_id),
                               run_date=run_date, name=func_qualname)
            return job_id
