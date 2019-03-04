def job_wrapper(id, func, *args, **kwargs):
    #TODO: jobtracker, update status to running and save start time 
    try:
        func(*args, **kwargs)
    except Exception as e:
        pass #TODO: save exception, update job status and finish time
    else:
        pass #TODO: save result(if possible/serializable), update job status and finish time

