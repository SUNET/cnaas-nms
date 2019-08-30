import traceback
from typing import Optional

from cnaas_nms.scheduler.jobtracker import Jobtracker
from cnaas_nms.scheduler.jobresult import JobResult
from cnaas_nms.tools.log import get_logger

logger = get_logger()


def find_nextjob(result: JobResult) -> Optional[str]:
    if isinstance(result, JobResult):
        return result.next_job_id if result.next_job_id else None


def insert_job_id(result: JobResult, job_id: str) -> JobResult:
    if isinstance(result, JobResult):
        if not result.job_id:
            result.job_id = job_id
    return result


def job_wrapper(func):
    """Decorator to save job status in job tracker database."""
    def wrapper(job_id: Optional[str]=None, *args, **kwargs):
        if job_id:
            job = Jobtracker()
            try:
                job.load(job_id)
            except:
                job = None
            else:
                kwargs['kwargs']['job_id'] = job_id
        if job:
            job.start(fname = func.__name__)
        try:
            # kwargs is contained in an item called kwargs because of the apscheduler.add_job call
            res = func(*args, **kwargs['kwargs'])
            if job_id:
                res = insert_job_id(res, job_id)
        except Exception as e:
            tb = traceback.format_exc()
            logger.debug("Exception traceback in job_wrapper: {}".format(tb))
            if job:
                job.finish_exception(e, tb)
            raise e
        else:
            if job:
                job.finish_success(res, find_nextjob(res))
            return res
    return wrapper

