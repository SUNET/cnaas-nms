import os
import yaml
import coverage
import atexit
import signal

from cnaas_nms.api import app
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.plugins.pluginmanager import PluginManagerHandler
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.joblock import Joblock
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.get_apidata import get_apidata


logger = get_logger()

os.environ['PYTHONPATH'] = os.getcwd()


if 'COVERAGE' in os.environ:
    cov = coverage.coverage(data_file='/coverage/.coverage-{}'.format(os.getpid()))
    cov.start()


    def save_coverage():
        cov.stop()
        cov.save()


    atexit.register(save_coverage)
    signal.signal(signal.SIGTERM, save_coverage)
    signal.signal(signal.SIGINT, save_coverage)


def get_app():
    # If running inside uwsgi, a separate "mule" will run the scheduler
    try:
        import uwsgi
        print("Running inside uwsgi")
    except (ModuleNotFoundError, ImportError):
        scheduler = Scheduler()
        scheduler.start()

    pmh = PluginManagerHandler()
    pmh.load_plugins()

    try:
        with sqla_session() as session:
            Joblock.clear_locks(session)
    except Exception as e:
        logger.exception("Unable to clear old locks from database at startup: {}".format(str(e)))

    return app.app


if __name__ == '__main__':
    apidata = get_apidata()
    if isinstance(apidata, dict) and 'host' in apidata:
        get_app().run(debug=True, host=apidata['host'])
    else:
        get_app().run(debug=True)
else:
    cnaas_app = get_app()
