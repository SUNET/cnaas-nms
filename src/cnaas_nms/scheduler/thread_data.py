import threading

thread_data = threading.local()


def set_thread_data(job_id):
    if job_id and type(job_id) == int:
        thread_data.job_id = job_id
