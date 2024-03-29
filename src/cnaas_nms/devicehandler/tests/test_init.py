import os
import time
import unittest

import pkg_resources
import yaml
from nornir.core.inventory import ConnectionOptions
from nornir_napalm.plugins.tasks import napalm_configure
from nornir_utils.plugins.functions import print_result

import cnaas_nms.devicehandler.init_device
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.job import Job
from cnaas_nms.db.session import sqla_session
from cnaas_nms.devicehandler.update import reset_interfacedb
from cnaas_nms.scheduler.scheduler import Scheduler


class InitTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, "data")
        with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)

        scheduler = Scheduler()
        scheduler.start()

    def tearDown(self):
        scheduler = Scheduler()
        ap_scheduler = scheduler.get_scheduler()
        time.sleep(1)
        for i in range(1, 11):
            num_scheduled_jobs = len(ap_scheduler.get_jobs())
            with sqla_session() as session:
                num_running_jobs = session.query(Job).count()
            print(
                "Number of jobs scheduled: {}, number of jobs running: {}".format(num_scheduled_jobs, num_running_jobs)
            )
            if num_scheduled_jobs > 0 or num_running_jobs > 0:
                print("Scheduled jobs still in queue: ")
                ap_scheduler.print_jobs()
                print("Sleeping 10 seconds")
                time.sleep(10)
            else:
                print("Shutting down scheduler")
                scheduler.shutdown()
                return
        scheduler.shutdown()

    def init_access_device(self):
        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            cnaas_nms.devicehandler.init_device.init_access_device_step1,
            when=0,
            scheduled_by="test_user",
            kwargs={
                "device_id": self.testdata["init_access_device_id"],
                "new_hostname": self.testdata["init_access_new_hostname"],
            },
        )
        print(f"Step1 scheduled as ID { job_id }")

    def reset_access_device(self):
        nr = cnaas_nms.devicehandler.nornir_helper.cnaas_init()
        nr_filtered = nr.filter(name=self.testdata["init_access_new_hostname"])
        nr_filtered.inventory.hosts[self.testdata["init_access_new_hostname"]].connection_options[
            "napalm"
        ] = ConnectionOptions(extras={"timeout": 5})

        data_dir = pkg_resources.resource_filename(__name__, "data")
        with open(os.path.join(data_dir, "access_reset.j2"), "r") as f_reset_config:
            print(self.testdata["init_access_new_hostname"])
            config = f_reset_config.read()
            print(config)
            nrresult = nr_filtered.run(
                task=napalm_configure,
                name="Reset config",
                replace=False,
                configuration=config,
                dry_run=False,  # TODO: temp for testing
            )
            print_result(nrresult)

        reset_interfacedb(self.testdata["init_access_new_hostname"])

        with sqla_session() as session:
            dev: Device = (
                session.query(Device).filter(Device.hostname == self.testdata["init_access_new_hostname"]).one()
            )
            dev.management_ip = None
            dev.hostname = self.testdata["init_access_old_hostname"]
            dev.state = DeviceState.DISCOVERED
            dev.device_type = DeviceType.UNKNOWN


if __name__ == "__main__":
    unittest.main()
