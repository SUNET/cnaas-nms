import json
import datetime
import os
import coverage
import atexit
import signal

from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.plugins.pluginmanager import PluginManagerHandler
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.joblock import Joblock
from cnaas_nms.db.job import Job, JobStatus
from cnaas_nms.tools.log import get_logger


logger = get_logger()
logger.info("Code coverage collection for mule in pid {}: {}".format(
    os.getpid(), ('COVERAGE' in os.environ)))

if 'COVERAGE' in os.environ:
    cov = coverage.coverage(data_file='/coverage/.coverage-{}'.format(os.getpid()))
    cov.start()


    def save_coverage():
        cov.stop()
        cov.save()


    atexit.register(save_coverage)
    signal.signal(signal.SIGTERM, save_coverage)
    signal.signal(signal.SIGINT, save_coverage)


def pre_schedule_checks(scheduler, kwargs):
    check_ok = True
    message = ""
    for job in scheduler.get_scheduler().get_jobs():
        # Only allow scheduling of one discover_device job at the same time
        if job.name == 'cnaas_nms.confpush.init_device:discover_device':
            if job.kwargs['kwargs']['ztp_mac'] == kwargs['kwargs']['ztp_mac']:
                message = ("There is already another scheduled job to discover device {}, skipping ".
                           format(kwargs['kwargs']['ztp_mac']))
                check_ok = False

    if not check_ok:
        logger.debug(message)
        with sqla_session() as session:
            job_entry: Job = session.query(Job).filter(Job.id == kwargs['job_id']).one_or_none()
            job_entry.finish_abort(message)

    return check_ok


def main_loop():
    try:
        import uwsgi
    except Exception as e:
        logger.exception("Mule not running in uwsgi, exiting: {}".format(str(e)))
        print("Error, not running in uwsgi")
        return

    print("Running scheduler in uwsgi mule")
    scheduler = Scheduler()
    scheduler.start()

    pmh = PluginManagerHandler()
    pmh.load_plugins()

    try:
        with sqla_session() as session:
            Joblock.clear_locks(session)
    except Exception as e:
        logger.exception("Unable to clear old locks from database at startup: {}".format(str(e)))

    while True:
        mule_data = uwsgi.mule_get_msg()
        data: dict = json.loads(mule_data)
        action = "add"
        if 'scheduler_action' in data:
            if data['scheduler_action'] == "remove":
                action = "remove"
        if data['when'] and isinstance(data['when'], int):
            data['run_date'] = datetime.datetime.utcnow() + datetime.timedelta(seconds=data['when'])
            del data['when']
        kwargs = {}
        for k, v in data.items():
            if k not in ['func', 'trigger', 'id', 'run_date', 'scheduler_action']:
                kwargs[k] = v
        # Perform pre-schedule job checks
        try:
            if action == "add" and not pre_schedule_checks(scheduler, kwargs):
                continue
        except Exception as e:
            logger.exception("Unable to perform pre-schedule job checks: {}".format(e))

        if action == "add":
            scheduler.add_local_job(data['func'], trigger=data['trigger'], kwargs=kwargs,
                                    id=data['id'], run_date=data['run_date'], name=data['func'])
        elif action == "remove":
            scheduler.remove_local_job(data['id'])


if __name__ == '__main__':
    main_loop()

