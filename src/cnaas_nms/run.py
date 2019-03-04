from cnaas_nms.api import app
from cnaas_nms.scheduler.scheduler import Scheduler

# Workaround for bug with reloader https://github.com/pallets/flask/issues/1246
import os
os.environ['PYTHONPATH'] = os.getcwd()

def main():
    scheduler = Scheduler()
    scheduler.start()
    app.run(debug=True)

if __name__ == '__main__':
    main()
