import traceback
import threading

from typing import Optional

from cnaas_nms.scheduler.jobtracker import Jobtracker
from cnaas_nms.scheduler.jobresult import JobResult
from cnaas_nms.tools.log import get_logger
from cnaas_nms.db.session import redis_session


logger = get_logger()


def find_nextjob(result: JobResult) -> Optional[str]:
    if isinstance(result, JobResult):
        return result.next_job_id if result.next_job_id else None


def insert_job_id(result: JobResult, job_id: str) -> JobResult:
    if isinstance(result, JobResult):
        if not result.job_id:
            result.job_id = job_id
    return result


def update_device_progress(stop_event: threading.Event, job: Jobtracker):
    while not stop_event.wait(2):
        finished_devices = job.finished_devices
        with redis_session() as db:
            while(db.llen('finished_devices_' + str(job.id)) != 0):
                last_finished = db.lpop('finished_devices_' + str(job.id)).decode('utf-8')
                finished_devices.append(last_finished)
        job.update({'finished_devices': finished_devices})


def job_wrapper(func):
    """Decorator to save job status in job tracker database."""
    def wrapper(job_id: Optional[str] = None, *args, **kwargs):
        progress_funcitons = ['sync_devices', 'device_upgrade']
        if job_id:
            job = Jobtracker()
            try:
                job.load(job_id)
            except Exception:
                job = None
            else:
                kwargs['kwargs']['job_id'] = job_id
        if job:
            job.start(fname=func.__name__)
            if func.__name__ in progress_funcitons:
                stop_event = threading.Event()
                device_thread = threading.Thread(target=update_device_progress,
                                                 args=(stop_event, job))
                device_thread.start()
        try:
            # kwargs is contained in an item called kwargs because of the apscheduler.add_job call
            res = func(*args, **kwargs['kwargs'])
            if job_id:
                res = insert_job_id(res, job_id)
        except Exception as e:
            tb = traceback.format_exc()
            logger.debug("Exception traceback in job_wrapper: {}".format(tb))
            if job:
                if func.__name__ in progress_funcitons:
                    stop_event.set()
                job.finish_exception(e, tb)
            raise e
        else:
            if job:
                if func.__name__ in progress_funcitons:
                    stop_event.set()
                job.finish_success(res, find_nextjob(res))
            return res
    return wrapper
