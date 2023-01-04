import unittest
import pkg_resources
import yaml
import os
import time

import pytest

from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.scheduler.jobresult import DictJobResult
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.job import Job, JobStatus


@job_wrapper
def job_testfunc_success(text='', job_id=None, scheduled_by=None):
    print(text)
    return DictJobResult(
        result = {'status': 'success'}
    )


@job_wrapper
def job_testfunc_exception(text='', job_id=None, scheduled_by=None):
    print(text)
    raise Exception("testfunc_exception raised exception")


@pytest.mark.integration
class InitTests(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def requirements(self, postgresql):
        """Ensures the required pytest fixtures are loaded implicitly for all these tests"""
        pass

    @classmethod
    def setUpClass(cls) -> None:
        scheduler = Scheduler()
        scheduler.start()

    @classmethod
    def tearDownClass(cls) -> None:
        scheduler = Scheduler()
        time.sleep(3)
        scheduler.get_scheduler().print_jobs()
        scheduler.shutdown()

    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)

    def test_add_schedule(self):
        scheduler = Scheduler()
        job1_id = scheduler.add_onetime_job(job_testfunc_success, when=1,
                                            scheduled_by='test_user',
                                            kwargs={'text': 'success'})
        job2_id = scheduler.add_onetime_job(job_testfunc_exception, when=1,
                                            scheduled_by='test_user',
                                            kwargs={'text': 'exception'})
        assert isinstance(job1_id, int)
        assert isinstance(job2_id, int)
        print(f"Test job 1 scheduled as ID { job1_id }")
        print(f"Test job 2 scheduled as ID { job2_id }")
        time.sleep(3)
        with sqla_session() as session:
            job1 = session.query(Job).filter(Job.id == job1_id).one_or_none()
            self.assertIsInstance(job1, Job, "Test job 1 could not be found")
            self.assertEqual(job1.status, JobStatus.FINISHED, "Test job 1 did not finish")
            self.assertEqual(job1.result, {'status': 'success'}, "Test job 1 returned bad status")
            job2 = session.query(Job).filter(Job.id == job2_id).one_or_none()
            self.assertIsInstance(job2, Job, "Test job 2 could not be found")
            self.assertEqual(job2.status, JobStatus.EXCEPTION, "Test job 2 did not make exception")
            self.assertIn("message", job2.exception, "Test job 2 did not contain message in exception")

    def test_abort_schedule(self):
        scheduler = Scheduler()
        job3_id = scheduler.add_onetime_job(job_testfunc_success, when=600,
                                            scheduled_by='test_user',
                                            kwargs={'text': 'abort'})
        assert isinstance(job3_id, int)
        print(f"Test job 3 scheduled as ID { job3_id }")
        scheduler.remove_scheduled_job(job3_id)
        time.sleep(3)
        with sqla_session() as session:
            job3 = session.query(Job).filter(Job.id == job3_id).one_or_none()
            self.assertIsInstance(job3, Job, "Test job 3 could not be found")
            self.assertEqual(job3.status, JobStatus.ABORTED, "Test job 3 did not abort")
            self.assertEqual(job3.result, {'message': 'removed'}, "Test job 3 returned bad status")


if __name__ == '__main__':
    unittest.main()
