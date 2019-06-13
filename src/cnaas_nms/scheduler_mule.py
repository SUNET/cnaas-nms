import json
import datetime
import os
import coverage
import atexit

from cnaas_nms.scheduler.scheduler import Scheduler


print("DEBUGENV: {}".format(os.environ['COVERAGE']))
if os.environ['COVERAGE']:
    cov = coverage.coverage(data_file='.coverage-{}'.format(os.getpid()))
    cov.start()


    def save_coverage():
        cov.stop()
        cov.save()


    atexit.register(save_coverage)


def main_loop():
    try:
        import uwsgi
    except:
        print("Error, not running in uwsgi")
        return

    print("Running scheduler in uwsgi mule")
    scheduler = Scheduler()
    scheduler.start()

    while True:
        mule_data = uwsgi.mule_get_msg()
        data: dict = json.loads(mule_data)
        if data['when'] and isinstance(data['when'], int):
            data['run_date'] = datetime.datetime.utcnow() + datetime.timedelta(seconds=data['when'])
            del data['when']
        kwargs = {}
        for k, v in data.items():
            if k not in ['func', 'trigger', 'id', 'run_date']:
                kwargs[k] = v
        scheduler.add_job(data['func'], trigger=data['trigger'], kwargs=kwargs,
                          id=data['id'], run_date=data['run_date'])


if __name__ == '__main__':
    main_loop()

