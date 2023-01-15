import atexit
import os
import signal
import threading
from typing import List

import coverage
from gevent import monkey
from gevent import signal as gevent_signal
from redis import StrictRedis

from cnaas_nms.app_settings import api_settings

# Do late imports for anything cnaas/flask related so we can do gevent monkey patch, see below


os.environ["PYTHONPATH"] = os.getcwd()
stop_websocket_threads = False


def is_coverage_enabled():
    return os.getenv("COVERAGE", "0").strip() not in ("0", "off", "false", "no")


print("Code coverage collection for worker in pid {}: {}".format(os.getpid(), is_coverage_enabled()))


if is_coverage_enabled():
    cov = coverage.coverage(data_file=".coverage-{}".format(os.getpid()), concurrency="gevent")
    cov.start()

    def save_coverage():
        cov.stop()
        cov.save()

    atexit.register(save_coverage)
    gevent_signal.signal(signal.SIGTERM, save_coverage)
    gevent_signal.signal(signal.SIGINT, save_coverage)


def get_app():
    from cnaas_nms.db.job import Job
    from cnaas_nms.db.joblock import Joblock
    from cnaas_nms.db.session import sqla_session
    from cnaas_nms.plugins.pluginmanager import PluginManagerHandler
    from cnaas_nms.scheduler.scheduler import Scheduler

    # If running inside uwsgi, a separate "mule" will run the scheduler
    try:
        import uwsgi  # noqa: F401

        print("Running inside uwsgi")  # noqa: T001
    except (ModuleNotFoundError, ImportError):
        scheduler = Scheduler()
        scheduler.start()

    pmh = PluginManagerHandler()
    pmh.load_plugins()

    try:
        with sqla_session() as session:
            Joblock.clear_locks(session)
    except Exception as e:
        print("Unable to clear old locks from database at startup: {}".format(str(e)))  # noqa: T001

    try:
        with sqla_session() as session:
            Job.clear_jobs(session)
    except Exception as e:
        print("Unable to clear jobs with invalid states: {}".format(str(e)))  # noqa: T001
    return app.app


def socketio_emit(message: str, rooms: List[str]):
    if not app.socketio:
        return
    for room in rooms:
        app.socketio.emit("events", message, room=room)


def loglevel_to_rooms(levelname: str) -> List[str]:
    if levelname == "DEBUG":
        return ["DEBUG"]
    elif levelname == "INFO":
        return ["DEBUG", "INFO"]
    elif levelname == "WARNING":
        return ["DEBUG", "INFO", "WARNING"]
    elif levelname == "ERROR":
        return ["DEBUG", "INFO", "WARNING", "ERROR"]
    elif levelname == "CRITICAL":
        return ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def parse_redis_event(event):
    try:
        # [stream, [(messageid, {datadict})]
        if event[0] == "events":
            return event[1][0][1]
    except Exception:  # noqa: S110
        return None


def emit_redis_event(event):
    try:
        if event["type"] == "log":
            socketio_emit(event["message"], loglevel_to_rooms(event["level"]))
        elif event["type"] == "update":
            socketio_emit(json.loads(event["json"]), ["update_{}".format(event["update_type"])])
    except Exception:  # noqa: S110
        pass


def thread_websocket_events():
    redis: StrictRedis
    with redis_session() as redis:
        while True:
            result = redis.xread({"events": b"$"}, count=10, block=200)
            for item in result:
                event = parse_redis_event(item)
                if not event:
                    continue
                emit_redis_event(event)
            if stop_websocket_threads:
                break


if __name__ == "__main__":
    # Starting via python run.py
    # gevent monkey patching required if you start flask with the auto-reloader (debug mode)
    monkey.patch_all()
    import json

    from cnaas_nms.api import app
    from cnaas_nms.db.session import redis_session

    t_websocket_events = threading.Thread(target=thread_websocket_events)
    t_websocket_events.start()

    app.socketio.run(get_app(), debug=True, host=api_settings.HOST)
    stop_websocket_threads = True
    t_websocket_events.join()

    if is_coverage_enabled():
        save_coverage()

else:
    # Starting via uwsgi
    import json

    from cnaas_nms.api import app
    from cnaas_nms.db.session import redis_session

    t_websocket_events = threading.Thread(target=thread_websocket_events)
    t_websocket_events.start()

    cnaas_app = get_app()

    if is_coverage_enabled():
        save_coverage()
