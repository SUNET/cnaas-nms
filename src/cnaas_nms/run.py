import os
import sys
import yaml

from cnaas_nms.api import app
from cnaas_nms.scheduler.scheduler import Scheduler


os.environ['PYTHONPATH'] = os.getcwd()

def get_apidata(config='/etc/cnaas-nms/api.yml'):
    with open(config, 'r') as api_file:
        return yaml.safe_load(api_file)

def get_app():
    scheduler = Scheduler()
    scheduler.start()
    return app.app


if __name__ == '__main__':
    apidata = get_apidata()
    if isinstance(apidata, dict) and 'host' in apidata:
        get_app().run(debug=True, host=apidata['host'])
    else:
        get_app().run(debug=True)
else:
    cnaas_app = get_app()
