from cnaas_nms.scheduler.scheduler import Scheduler


print("Running scheduler in uwsgi mule")
scheduler = Scheduler()
scheduler.start()
