import inspect
import datetime
import fcntl
import os
import json
from pytz import utc
from typing import Optional, Union
from types import FunctionType

from apscheduler.schedulers.background import BackgroundScheduler, BlockingScheduler
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

    def add_job(self, func, **kwargs):
        return self._scheduler.add_job(func, **kwargs)

    def add_onetime_job(self, func: Union[str, FunctionType],
                        when: Optional[int] = None, **kwargs) -> int:
        """Schedule a job to run at a later time.

        Args:
            func: The function to call
            when: Optional number of seconds to wait before starting job
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

        with sqla_session() as session:
            job = Job()
            if run_date:
                job.scheduled_time = run_date
            session.add(job)
            session.flush()
            job_id = job.id

        kwargs['job_id'] = job_id
        if self.use_mule:
            try:
                import uwsgi
            except Exception as e:
                logger.exception("use_mule is set but not running in uwsgi")
                raise e
            args = dict(kwargs)
            if isinstance(func, FunctionType):
                args['func'] = str(func.__qualname__)
            else:
                args['func'] = str(func)
            args['trigger'] = trigger
            args['when'] = when
            args['id'] = str(job_id)
            uwsgi.mule_msg(json.dumps(args))
            return job_id
        else:
            self._scheduler.add_job(
                func, trigger=trigger, kwargs=kwargs, id=str(job_id), run_date=run_date)
            return job_id
