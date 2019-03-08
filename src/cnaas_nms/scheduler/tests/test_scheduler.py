
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.scheduler.jobresult import DictJobResult
from cnaas_nms.tools.printlastjobs import print_jobs

from apscheduler.job import Job

import pprint
import unittest
import pkg_resources
import yaml
import os
import time

@job_wrapper
def testfunc_success(text=''):
    print(text)
    return DictJobResult(
        result = {'status': 'success'}
    )

@job_wrapper
def testfunc_exception(text=''):
    print(text)
    raise Exception("testfunc_exception raised exception")

class InitTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.load(f_testdata)

        scheduler = Scheduler()
        scheduler.start()

    def tearDown(self):
        scheduler = Scheduler()
        time.sleep(3)
        scheduler.get_scheduler().print_jobs()
        print_jobs(2)
        scheduler.shutdown()

    def test_add_schedule(self):
        scheduler = Scheduler()
        job1 = scheduler.add_onetime_job(testfunc_success, when=1, kwargs={'text': 'success'})
        job2 = scheduler.add_onetime_job(testfunc_exception, when=1, kwargs={'text': 'exception'})
        assert isinstance(job1, Job)
        assert isinstance(job2, Job)
        print(f"Job1 scheduled as ID { job1.id }")
        print(f"Job2 scheduled as ID { job2.id }")


if __name__ == '__main__':
    unittest.main()
