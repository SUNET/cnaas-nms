
from cnaas_nms.scheduler.jobtracker import Jobtracker
import pprint
import sys

def print_jobs(num=1):
    for job in Jobtracker.get_last_entries(num_entries=num):
        jt = Jobtracker()
        jt.from_dict(job)
        pprint.pprint(jt.to_dict())

#        pprint.pprint(job)

if __name__ == "__main__":
    if len(sys.argv) == 2:
        print_jobs(int(sys.argv[1]))
    else:
        print_jobs()
