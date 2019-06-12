import json

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
        scheduler.add_job(**data)


if __name__ == '__main__':
    main_loop()

