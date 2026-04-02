import atexit
import datetime
import json
import os
import signal
from typing import Optional

from cnaas_nms.db.job import Job
from cnaas_nms.db.joblock import Joblock
from cnaas_nms.db.session import sqla_session
from cnaas_nms.plugins.pluginmanager import PluginManagerHandler
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.tools.log import get_logger

logger = get_logger()


def is_coverage_enabled():
    return os.getenv("COVERAGE", "0").strip() not in ("0", "off", "false", "no")


logger.info("Code coverage collection for mule in pid {}: {}".format(os.getpid(), is_coverage_enabled()))

if is_coverage_enabled():
    import coverage

    cov = coverage.coverage(data_file=".coverage-{}".format(os.getpid()))
    cov.start()

    def save_coverage() -> None:
        cov.stop()
        try:
            cov.save()
        except Exception as e:
            print("Failed to save coverage: {}".format(e))

    def save_coverage_signal(signum, frame) -> None:
        cov.stop()
        try:
            cov.save()
        except Exception as e:
            print("Failed to save coverage: {}".format(e))

    atexit.register(save_coverage)
    signal.signal(signal.SIGTERM, save_coverage_signal)  # type: ignore
    signal.signal(signal.SIGINT, save_coverage_signal)  # type: ignore


def pre_schedule_checks(scheduler, kwargs):
    check_ok = True
    message = ""
    for job in scheduler.get_scheduler().get_jobs():
        # Only allow scheduling of one discover_device job at the same time
        if job.name == "cnaas_nms.devicehandler.init_device:discover_device":
            if job.kwargs["kwargs"]["dhcp_ip"] == kwargs["kwargs"]["dhcp_ip"]:
                message = "There is already another scheduled job to discover {} {}, skipping ".format(
                    kwargs["kwargs"]["ztp_mac"], kwargs["kwargs"]["dhcp_ip"]
                )
                check_ok = False

    if not check_ok:
        logger.debug(message)
        with sqla_session() as session:  # type: ignore
            job_entry: Optional[Job] = session.query(Job).filter(Job.id == kwargs["job_id"]).one_or_none()
            if job_entry:
                job_entry.finish_abort(message)

    return check_ok


def main_loop() -> None:
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
        with sqla_session() as session:  # type: ignore
            Joblock.clear_locks(session)
    except Exception as e:
        logger.exception("Unable to clear old locks from database at startup: {}".format(str(e)))

    while True:
        mule_data = uwsgi.mule_get_msg()
        try:
            data: dict = json.loads(mule_data)
        except json.JSONDecodeError as e:
            logger.exception("Mule received non-JSON data: {}".format(e))
            logger.debug("Mule received data: {}".format(mule_data))
            continue
        action = "add"
        if "scheduler_action" in data:
            if data["scheduler_action"] == "remove":
                action = "remove"
            elif data["scheduler_action"] == "shutdown_mule":
                action = "shutdown_mule"
        if "when" in data and isinstance(data["when"], int):
            data["run_date"] = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) + datetime.timedelta(
                seconds=data["when"]
            )
            del data["when"]
        kwargs = {}
        for k, v in data.items():
            if k not in ["func", "trigger", "id", "run_date", "scheduler_action"]:
                kwargs[k] = v
        # Perform pre-schedule job checks
        try:
            if action == "add" and not pre_schedule_checks(scheduler, kwargs):
                continue
        except Exception as e:
            logger.exception("Unable to perform pre-schedule job checks: {}".format(e))

        if action == "add":
            scheduler.add_local_job(
                data["func"],
                trigger=data["trigger"],
                kwargs=kwargs,
                id=data["id"],
                run_date=data["run_date"],
                name=data["func"],
                misfire_grace_time=5,
            )
        elif action == "remove":
            scheduler.remove_local_job(data["id"])
        elif action == "shutdown_mule":
            scheduler.get_scheduler().shutdown()
            return


if __name__ == "__main__":
    main_loop()
