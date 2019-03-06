
from cnaas_nms.cmdb.session import mongo_db
import pprint
import sys

#db.jobs.find().sort({_id:-1}).limit(2);

def print_jobs(num=1):
    with mongo_db() as db:
        jobs = db['jobs']
        data = jobs.find().sort('_id', -1).limit(num)
        for job in data:
            pprint.pprint(job)

if __name__ == "__main__":
    print_jobs(int(sys.argv[1]))
