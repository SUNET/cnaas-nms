import cnaas_nms.confpush.init_device
from cnaas_nms.scheduler.scheduler import Scheduler

import pprint
import unittest
import pkg_resources
import yaml
import os
import time

class InitTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.load(f_testdata)

        scheduler = Scheduler()
        scheduler.start()

    def tearDown(self):
        scheduler = Scheduler()
        time.sleep(70)
        scheduler.get_scheduler().print_jobs()
        scheduler.shutdown()

    def test_init_access_device(self):
        scheduler = Scheduler()
        job = scheduler.add_onetime_job(
            cnaas_nms.confpush.init_device.init_access_device_step1,
            when=1,
            kwargs={'device_id': 6, 'new_hostname': 'eosaccess'})
        print(f"Step1 scheduled as ID { job.id }")


if __name__ == '__main__':
    unittest.main()
