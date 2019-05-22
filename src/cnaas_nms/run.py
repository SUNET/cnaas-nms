import yaml

from cnaas_nms.api import app
from cnaas_nms.scheduler.scheduler import Scheduler

# Workaround for bug with reloader https://github.com/pallets/flask/issues/1246
import os
os.environ['PYTHONPATH'] = os.getcwd()


def get_apidata(config='/etc/cnaas-nms/api.yml'):
    with open(config, 'r') as api_file:
        return yaml.safe_load(api_file)


def main():
    #TODO: create lockfile? also clear all jobs that have state running before starting scheduler
    scheduler = Scheduler()
    scheduler.start()
    apidata = get_apidata()
    if isinstance(apidata, dict) and 'host' in apidata:
        app.app.run(debug=True, host=apidata['host'])
    else:
        app.app.run(debug=True)


if __name__ == '__main__':
    main()
