import traceback
import threading

from typing import Optional

from cnaas_nms.db.job import Job
from cnaas_nms.scheduler.jobresult import JobResult
from cnaas_nms.tools.log import get_logger
from cnaas_nms.db.session import redis_session
from cnaas_nms.db.session import sqla_session
from cnaas_nms.scheduler.thread_data import thread_data, set_thread_data


logger = get_logger()


def find_nextjob(result: JobResult) -> Optional[int]:
    if isinstance(result, JobResult):
        return result.next_job_id if result.next_job_id else None


def insert_job_id(result: JobResult, job_id: int) -> JobResult:
    if isinstance(result, JobResult):
        if not result.job_id:
            result.job_id = job_id
    return result


def update_device_progress(job_id: int):
    new_finished_devices = []
    with redis_session() as db:
        while db.llen('finished_devices_' + str(job_id)) != 0:
            last_finished = db.lpop('finished_devices_' + str(job_id))
            new_finished_devices.append(last_finished)

    if new_finished_devices:
        with sqla_session() as session:
            job = session.query(Job).filter(Job.id == job_id).one_or_none()
            if not job:
                raise ValueError("Could not find Job with ID {}".format(job_id))
            finished_devices = job.finished_devices + new_finished_devices
            job.finished_devices = finished_devices


def update_device_progress_thread(stop_event: threading.Event, job_id: int):
    while not stop_event.wait(2):
        update_device_progress(job_id)
    update_device_progress(job_id)  # update one last time before exiting thread


def job_wrapper(func):
    """Decorator to save job status in job tracker database."""
    def wrapper(job_id: int, scheduled_by: str, kwargs={}):
        if not job_id or not type(job_id) == int:
            errmsg = "Missing job_id when starting job for {}".format(func.__name__)
            logger.error(errmsg)
            raise ValueError(errmsg)
        progress_funcitons = ['sync_devices', 'device_upgrade']
        with sqla_session() as session:
            job = session.query(Job).filter(Job.id == job_id).one_or_none()
            if not job:
                errmsg = "Could not find job_id {} in database".format(job_id)
                logger.error(errmsg)
                raise ValueError(errmsg)
            kwargs['job_id'] = job_id
            # Don't send new function name unless it was set to "wrapper"
            function_name = None
            if job.function_name == "wrapper":
                function_name = func.__name__
            job.start_job(function_name=function_name)
            if func.__name__ in progress_funcitons:
                stop_event = threading.Event()
                device_thread = threading.Thread(target=update_device_progress_thread,
                                                 args=(stop_event, job_id))
                device_thread.start()
        try:
            set_thread_data(job_id)
            # kwargs is contained in an item called kwargs because of the apscheduler.add_job call
            res = func(**kwargs)
            if job_id:
                res = insert_job_id(res, job_id)
            del thread_data.job_id
        except Exception as e:
            tb = traceback.format_exc()
            logger.debug("Exception traceback in job_wrapper: {}".format(tb))
            with sqla_session() as session:
                job = session.query(Job).filter(Job.id == job_id).one_or_none()
                if not job:
                    errmsg = "Could not find job_id {} in database".format(job_id)
                    logger.error(errmsg)
                    raise ValueError(errmsg)
                if func.__name__ in progress_funcitons:
                    stop_event.set()
                job.finish_exception(e, tb)
                session.commit()
            raise e
        else:
            if func.__name__ in progress_funcitons:
                stop_event.set()
                device_thread.join()
            with sqla_session() as session:
                job = session.query(Job).filter(Job.id == job_id).one_or_none()
                if not job:
                    errmsg = "Could not find job_id {} in database".format(job_id)
                    logger.error(errmsg)
                    raise ValueError(errmsg)
                job.finish_success(res, find_nextjob(res))
                session.commit()
            return res
    return wrapper
