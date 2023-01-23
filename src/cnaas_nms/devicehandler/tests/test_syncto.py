import logging
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


def run_syncto_job(scheduler, testdata: dict, dry_run: bool = True) -> Optional[dict]:
    job_id = scheduler.add_onetime_job(
        sync_devices,
        when=0,
        scheduled_by="test_user",
        kwargs={
            "hostnames": testdata["syncto_device_hostnames"],
            "dry_run": dry_run,
            "resync": True,
        },
    )
    job_res: Optional[Job] = None
    job_dict: Optional[dict] = None
    jobstatus_wait = [JobStatus.SCHEDULED, JobStatus.RUNNING]
    with sqla_session() as session:
        for i in range(1, 30):
            time.sleep(1)
            if not job_res or job_res.status in jobstatus_wait:
                job_res: Job = session.query(Job).filter(Job.id == job_id).one()
                job_dict = job_res.as_dict()
                # if next_job_id scheduled for confirm action, wait for that also
                if job_res.next_job_id:
                    next_job_res = Optional[Job] = None
                    for j in range(1, 30):
                        time.sleep(1)
                        if not next_job_res or next_job_res.status in jobstatus_wait:
                            next_job_res = session.query(Job).filter(Job.id == job_res.next_job_id).one()
                        else:
                            break
            else:
                print("test run_syncto_job run {} status {}".format(i, JobStatus.name))
                break
    return job_dict


@pytest.mark.equipment
def test_syncto_commitmode_0(testdata, scheduler, settings_directory, templates_directory, postgresql, redis, caplog):
    api_settings.COMMIT_CONFIRMED_MODE = 0
    api_settings.SETTINGS_OVERRIDE = testdata["syncto_settings_override"]
    with caplog.at_level(logging.DEBUG):
        job_dict = run_syncto_job(scheduler, testdata)
        hostname = testdata["syncto_device_hostnames"][0]
        assert f"Commit confirm mode for host {hostname}: 0" in caplog.text
    assert job_dict["status"] == "FINISHED"
    assert job_dict["result"]["devices"][hostname]["failed"] is False


@pytest.mark.equipment
def test_syncto_commitmode_1(testdata, scheduler, settings_directory, templates_directory, postgresql, redis, caplog):
    api_settings.COMMIT_CONFIRMED_MODE = 1
    api_settings.SETTINGS_OVERRIDE = testdata["syncto_settings_override"]
    with caplog.at_level(logging.DEBUG):
        job_dict = run_syncto_job(scheduler, testdata)
        hostname = testdata["syncto_device_hostnames"][0]
        assert f"Commit confirm mode for host {hostname}: 1" in caplog.text
    assert job_dict["status"] == "FINISHED"
    assert job_dict["result"]["devices"][hostname]["failed"] is False


@pytest.mark.equipment
def test_syncto_commitmode_2(testdata, scheduler, settings_directory, templates_directory, postgresql, redis, caplog):
    api_settings.COMMIT_CONFIRMED_MODE = 2
    api_settings.SETTINGS_OVERRIDE = testdata["syncto_settings_override"]
    with caplog.at_level(logging.DEBUG):
        job_dict = run_syncto_job(scheduler, testdata, dry_run=False)
        hostname = testdata["syncto_device_hostnames"][0]
        assert f"Commit confirm mode for host {hostname}: 2" in caplog.text
    assert job_dict["status"] == "FINISHED"
    assert job_dict["result"]["devices"][hostname]["failed"] is False

    # Revert change
    api_settings.SETTINGS_OVERRIDE = None
    with caplog.at_level(logging.DEBUG):
        job_dict = run_syncto_job(scheduler, testdata, dry_run=False)
        assert "selected for commit-confirm" in caplog.text
    assert job_dict["status"] == "FINISHED"
    assert job_dict["result"]["devices"][hostname]["failed"] is False
