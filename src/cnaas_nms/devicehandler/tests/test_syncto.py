import os
import time
from typing import Optional

import pkg_resources
import pytest
import yaml
from apscheduler.schedulers.base import STATE_STOPPED

from cnaas_nms.db.job import Job, JobStatus
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.settings import api_settings
from cnaas_nms.devicehandler.sync_devices import sync_devices
from cnaas_nms.scheduler.scheduler import Scheduler


@pytest.fixture
def testdata(scope="session"):
    data_dir = pkg_resources.resource_filename(__name__, "data")
    with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
        return yaml.safe_load(f_testdata)


@pytest.fixture
def scheduler(scope="session"):
    scheduler = Scheduler()
    if scheduler.get_scheduler().state == STATE_STOPPED:
        scheduler.start()
    return scheduler


@pytest.mark.integration
def test_syncto_commitmode_1(testdata, scheduler):
    api_settings.COMMIT_CONFIRMED_MODE = 1
    api_settings.SETTINGS_OVERRIDE = {"cli_append_str": "interface Management1\ndescription test"}
    job_id = scheduler.add_onetime_job(
        sync_devices,
        when=0,
        scheduled_by="test_user",
        kwargs={
            "hostnames": ["eosdist1"],
        },
    )
    job_res: Optional[Job] = None
    job_dict: Optional[dict] = None
    with sqla_session() as session:
        time.sleep(2)
        for i in range(1, 5):
            if not job_res or job_res.status == JobStatus.SCHEDULED or job_res.status == JobStatus.RUNNING:
                job_res = session.query(Job).filter(Job.id == job_id).one()
                job_dict = job_res.as_dict()
            else:
                break
    assert job_dict["status"] == "FINISHED"
    assert job_dict["result"]["devices"]["eosdist1"]["failed"] is False
