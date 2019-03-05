import traceback

from cnaas_nms.scheduler.jobtracker import Jobtracker

from typing import Optional

def job_wrapper(func):
    """Decorator to save job status in job tracker database."""
    def wrapper(job_id: Optional[str]=None, *args, **kwargs):
        if job_id:
            job = Jobtracker()
            try:
                job.load(job_id)
            except:
                job = None
        if job:
            job.start()
        try:
            # kwargs is contained in an item called kwargs because of the apscheduler.add_job call
            res = func(*args, **kwargs['kwargs'])
        except Exception as e:
            tb = traceback.format_exc()
            if job:
                job.finish_exception(e, tb)
            raise e
        else:
            if job:
                job.finish_success(res)
            return res
    return wrapper

