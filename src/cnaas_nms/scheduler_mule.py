import json
import datetime

from cnaas_nms.scheduler.scheduler import Scheduler


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
        data = json.loads(mule_data)
        if data['when'] and isinstance(data['when'], int):
            data['run_date'] = datetime.datetime.utcnow() + datetime.timedelta(seconds=data['when'])
            del data['when']
        scheduler.add_job(**data)


if __name__ == '__main__':
    main_loop()

