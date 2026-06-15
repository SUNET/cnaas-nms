import os
import time
import unittest
from ipaddress import IPv4Address
from pathlib import Path
from unittest.mock import MagicMock, patch

from nornir.core.inventory import ConnectionOptions
from nornir_napalm.plugins.tasks import napalm_configure
from nornir_utils.plugins.functions import print_result
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

import cnaas_nms.devicehandler.init_device
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.db.job import Job
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.reservedip import ReservedIP
from cnaas_nms.db.session import sqla_session
from cnaas_nms.devicehandler.update import reset_interfacedb
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.tools.yaml import yaml_safe_load


class InitTests(unittest.TestCase):
    def setUp(self):
        data_dir = Path(__file__).parent / "data"
        with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
            self.testdata = yaml_safe_load(f_testdata)

        scheduler = Scheduler()
        scheduler.start()

    def tearDown(self):
        scheduler = Scheduler()
        ap_scheduler = scheduler.get_scheduler()
        time.sleep(1)
        for i in range(1, 11):
            num_scheduled_jobs = len(ap_scheduler.get_jobs())
            with sqla_session() as session:  # type: ignore
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
        print(f"Step1 scheduled as ID {job_id}")

    def reset_access_device(self):
        nr = cnaas_nms.devicehandler.nornir_helper.cnaas_init()
        nr_filtered = nr.filter(name=self.testdata["init_access_new_hostname"])
        nr_filtered.inventory.hosts[self.testdata["init_access_new_hostname"]].connection_options["napalm"] = (
            ConnectionOptions(extras={"timeout": 5})
        )

        data_dir = Path(__file__).parent / "data"
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

        with sqla_session() as session:  # type: ignore
            dev: Device = (
                session.query(Device).filter(Device.hostname == self.testdata["init_access_new_hostname"]).one()
            )
            dev.management_ip = None
            dev.hostname = self.testdata["init_access_old_hostname"]
            dev.state = DeviceState.DISCOVERED
            dev.device_type = DeviceType.UNKNOWN


class InitDeviceTests(unittest.TestCase):
    def cleandb(self):
        with sqla_session() as session:  # type: ignore
            for hostname in [
                "uplink_a1",
                "discovered_a1",
                "discovered_a2",
            ]:
                device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
                if device:
                    session.query(Linknet).filter(
                        or_(Linknet.device_a_id == device.id, Linknet.device_b_id == device.id)
                    ).delete()
                    session.query(Interface).filter(Interface.device_id == device.id).delete()
                    session.delete(device)

            res_ip = session.query(ReservedIP).filter(ReservedIP.ip == "10.0.6.101").one_or_none()
            if res_ip:
                session.delete(res_ip)

            session.commit()

    def setUp(self):
        self.cleandb()

    def tearDown(self):
        self.cleandb()

    @patch("cnaas_nms.db.helper.find_mgmtdomain")
    @patch("cnaas_nms.devicehandler.init_device.check_neighbor_sync")
    @patch("cnaas_nms.devicehandler.init_device.pre_init_check_neighbors")
    @patch("cnaas_nms.devicehandler.init_device.update_interfacedb_worker")
    @patch("cnaas_nms.devicehandler.init_device.update_linknets")
    @patch("cnaas_nms.devicehandler.init_device.pre_init_checks")
    def test_init_access_conflicting_mgmt_ip(
        self,
        mock_pre_init,
        mock_update_linknets,
        mock_update_interfacedb_worker,
        mock_pre_init_check_neighbors,
        mock_check_neighbor_sync,
        mock_find_mgmtdomain,
    ):
        def mocked_pre_init(session, device_id: int) -> Device:
            dev: Device = session.query(Device).filter(Device.id == device_id).one_or_none()
            return dev

        mock_pre_init.side_effect = mocked_pre_init

        # Mock mgmtdomain and force return the same IP as dev1 reservedip.
        mock_mgmtdomain_instance = MagicMock()

        mock_mgmtdomain_instance.is_dual_stack = False

        mock_mgmtdomain_instance.find_free_primary_mgmt_ip.return_value = IPv4Address("10.0.6.101")

        mock_find_mgmtdomain.return_value = mock_mgmtdomain_instance

        mock_update_linknets.return_value = {}

        mock_update_interfacedb_worker.return_value = None

        mock_pre_init_check_neighbors.return_value = ["uplink_a1"]

        mock_check_neighbor_sync.return_value = MagicMock()

        init_func = cnaas_nms.devicehandler.init_device.init_access_device_step1.__wrapped__

        # Prepare test data.
        with sqla_session() as session:  # type: ignore
            uplink_dev = Device(
                management_ip="10.0.6.100",
                hostname="uplink_a1",
                platform="eos",
                state=DeviceState.MANAGED,
                device_type=DeviceType.ACCESS,
            )

            # Add 2 Discovered Device
            dev1 = Device(
                management_ip=None,
                hostname="discovered_a1",
                platform="eos",
                state=DeviceState.DISCOVERED,
                device_type=DeviceType.UNKNOWN,
            )

            dev2 = Device(
                management_ip=None,
                hostname="discovered_a2",
                platform="eos",
                state=DeviceState.DISCOVERED,
                device_type=DeviceType.UNKNOWN,
            )
            session.add(uplink_dev)
            session.add(dev1)
            session.add(dev2)
            session.commit()
            session.refresh(uplink_dev)
            session.refresh(dev1)

            # Add Downlink ports to uplink_dev
            downlink_interface = Interface(
                device_id=uplink_dev.id, name="Ethernet1", configtype=InterfaceConfigType.ACCESS_DOWNLINK
            )
            session.add(downlink_interface)

            # Add Uplink port to dev2
            uplink_interface = Interface(
                device_id=dev2.id, name="Ethernet1", configtype=InterfaceConfigType.ACCESS_UPLINK
            )
            session.add(uplink_interface)

            # Add Reserved IP to dev1
            res_ip = ReservedIP(device_id=dev1.id, ip="10.0.6.101")
            session.add(res_ip)
            session.commit()

            # Try to init dev2 and force the same IP as dev1 simulating a conflict that might happen due to a race condition
            with self.assertRaises(IntegrityError) as context:
                init_func(device_id=dev2.id, new_hostname="managed_a1")

            self.assertIn("psycopg2.errors.UniqueViolation", str(context.exception))


if __name__ == "__main__":
    unittest.main()
