import inspect
import datetime
import fcntl
from pytz import utc
from typing import Optional, Union
from types import FunctionType

from apscheduler.schedulers.background import BackgroundScheduler, BlockingScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

import cnaas_nms.db.session
from cnaas_nms.scheduler.jobtracker import Jobtracker, JobStatus
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
        # If scheduler is already started, run with no executor threads
        self.lock_f = open('/tmp/scheduler.lock', 'w')
        try:
            fcntl.lockf(self.lock_f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            threads = 0
        else:
            threads = 10
        caller = self.get_caller(caller=inspect.currentframe())
        if caller == 'api':
            sqlalchemy_url = cnaas_nms.db.session.get_sqlalchemy_conn_str()
            self._scheduler = BackgroundScheduler(
                executors={'default': ThreadPoolExecutor(threads)},
                jobstores={'default': SQLAlchemyJobStore(url=sqlalchemy_url)},
                job_defaults={},
                timezone=utc
            )
            logger.info("Scheduler started with persistent jobstore, {} threads".format(threads))
        elif caller == 'mule':
            sqlalchemy_url = cnaas_nms.db.session.get_sqlalchemy_conn_str()
            self._scheduler = BlockingScheduler(
                executors={'default': ThreadPoolExecutor(threads)},
                jobstores={'default': SQLAlchemyJobStore(url=sqlalchemy_url)},
                job_defaults={},
                timezone=utc
            )
            logger.info("Scheduler started with persistent jobstore, {} threads".format(threads))
        elif threads == 0:
            sqlalchemy_url = cnaas_nms.db.session.get_sqlalchemy_conn_str()
            self._scheduler = BackgroundScheduler(
                executors={'default': ThreadPoolExecutor(threads)},
                jobstores={'default': SQLAlchemyJobStore(url=sqlalchemy_url)},
                job_defaults={},
                timezone=utc
            )
            logger.info("Scheduler started with persistent jobstore, {} threads".format(threads))
        else:
            self._scheduler = BackgroundScheduler(
                executors={'default': ThreadPoolExecutor(threads)},
                jobstores={'default': MemoryJobStore()},
                job_defaults={},
                timezone=utc
            )
            logger.info("Scheduler started with in-memory jobstore, {} threads".format(threads))

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
        return self._scheduler.start()

    def shutdown(self):
        return self._scheduler.shutdown()

    def add_job(self, func, **kwargs):
        return self._scheduler.add_job(func, **kwargs)

    def add_onetime_job(self, func: Union[str, FunctionType], when: Optional[int]=None, **kwargs):
        """Schedule a job to run at a later time.

        Args:
            func: The function to call
            when: Optional number of seconds to wait before starting job
            **kwargs: Arguments to pass through to called function
        Returns:
            apscheduler.job.Job
        """
        job = Jobtracker()
        id = job.create({'status': JobStatus.SCHEDULED})
        if when and isinstance(when, int):
            trigger = 'date'
            run_date = datetime.datetime.utcnow() + datetime.timedelta(seconds=when)
        else:
            trigger = None
            run_date = None
        kwargs['job_id'] = id
        return self._scheduler.add_job(
            func, trigger=trigger, kwargs=kwargs, id=id, run_date=run_date)

