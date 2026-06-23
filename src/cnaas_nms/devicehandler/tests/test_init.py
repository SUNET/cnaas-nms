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
from cnaas_nms.api import app
from cnaas_nms.api.tests.app_wrapper import TestAppWrapper
from cnaas_nms.db.device import Device, DeviceError, DeviceState, DeviceType
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.db.job import Job
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.reservedip import ReservedIP
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.stackmember import Stackmember
from cnaas_nms.devicehandler.update import reset_interfacedb, update_interfacedb_worker
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
                "uplink-a1",
                "discovered-a1",
                "discovered-a2",
                "mlag-a1",
                "mlag-a2",
                "mlag-replacement",
                "stack-a1",
                "stack-replacement",
                "uplink-a2",
                "replaced-switch-with-orphaned-uplink",
            ]:
                device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
                if device:
                    session.query(Linknet).filter(
                        or_(Linknet.device_a_id == device.id, Linknet.device_b_id == device.id)
                    ).delete()
                    session.query(Interface).filter(Interface.device_id == device.id).delete()
                    session.query(Stackmember).filter(Stackmember.device_id == device.id).delete()
                    session.delete(device)

            res_ip = session.query(ReservedIP).filter(ReservedIP.ip == "10.0.6.101").one_or_none()  # noqa: S1313
            if res_ip:
                session.delete(res_ip)

            session.commit()

    def setUp(self):
        self.cleandb()

        self.jwt_auth_token = None
        data_dir = Path(__file__).parent / "data"
        with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
            self.testdata = yaml_safe_load(f_testdata)
            if "jwt_auth_token" in self.testdata:
                self.jwt_auth_token = self.testdata["jwt_auth_token"]
        self.app = app.app
        self.app.wsgi_app = TestAppWrapper(self.app.wsgi_app, self.jwt_auth_token)
        self.client = self.app.test_client()

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

        mock_mgmtdomain_instance.find_free_primary_mgmt_ip.return_value = IPv4Address("10.0.6.101")  # noqa: S1313

        mock_find_mgmtdomain.return_value = mock_mgmtdomain_instance

        mock_update_linknets.return_value = {}

        mock_update_interfacedb_worker.return_value = None

        mock_pre_init_check_neighbors.return_value = ["uplink-a1"]

        mock_check_neighbor_sync.return_value = MagicMock()

        init_func = cnaas_nms.devicehandler.init_device.init_access_device_step1.__wrapped__

        # Prepare test data.
        with sqla_session() as session:  # type: ignore
            uplink_dev = Device(
                management_ip="10.0.6.100",  # noqa: S1313
                hostname="uplink-a1",
                platform="eos",
                state=DeviceState.MANAGED,
                device_type=DeviceType.ACCESS,
            )

            # Add 2 Discovered Device
            dev1 = Device(
                management_ip=None,
                hostname="discovered-a1",
                platform="eos",
                state=DeviceState.DISCOVERED,
                device_type=DeviceType.UNKNOWN,
            )

            dev2 = Device(
                management_ip=None,
                hostname="discovered-a2",
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
            res_ip = ReservedIP(device_id=dev1.id, ip="10.0.6.101")  # noqa: S1313
            session.add(res_ip)
            session.commit()

            # Try to init dev2 and force the same IP as dev1 simulating a conflict that might happen due to a race condition
            with self.assertRaises(IntegrityError) as context:
                init_func(device_id=dev2.id, new_hostname="managed_a1")

            self.assertIn("psycopg2.errors.UniqueViolation", str(context.exception))

    @patch("cnaas_nms.devicehandler.init_device.pre_init_checks")
    def test_init_access_mlag_error(
        self,
        mock_pre_init,
    ):
        """Test that when trying to replace a mlag switch it raises an exception"""

        def mocked_pre_init(session, device_id: int) -> Device:
            dev: Device = session.query(Device).filter(Device.id == device_id).one_or_none()
            return dev

        mock_pre_init.side_effect = mocked_pre_init

        init_func = cnaas_nms.devicehandler.init_device.init_access_device_step1.__wrapped__

        # Prepare test data.
        with sqla_session() as session:  # type: ignore
            mlag_a1 = Device(
                hostname="mlag-a1",
                platform="eos",
                state=DeviceState.UNMANAGED,  # UNMANAGED
                device_type=DeviceType.ACCESS,
            )
            mlag_a2 = Device(
                hostname="mlag-a2",
                platform="eos",
                state=DeviceState.MANAGED,
                device_type=DeviceType.ACCESS,
            )
            mlag_replacement = Device(
                hostname="mlag-replacement",
                platform="eos",
                state=DeviceState.DISCOVERED,
                device_type=DeviceType.UNKNOWN,
            )
            session.add(mlag_a1)
            session.add(mlag_a2)
            session.add(mlag_replacement)
            session.commit()
            session.refresh(mlag_a1)
            session.refresh(mlag_a2)
            session.refresh(mlag_replacement)

            mlag_replacement_id = mlag_replacement.id

            # Add MLAG ports
            # Interfaces
            interface_a1 = Interface(device_id=mlag_a1.id, name="Ethernet1", configtype=InterfaceConfigType.MLAG_PEER)
            interface_a2 = Interface(device_id=mlag_a2.id, name="Ethernet1", configtype=InterfaceConfigType.MLAG_PEER)
            session.add(interface_a1)
            session.add(interface_a2)

            # Linknet
            session.add(
                Linknet(
                    device_a=mlag_a1,
                    device_a_port=interface_a1.name,
                    device_b=mlag_a2,
                    device_b_port=interface_a2.name,
                )
            )

            session.commit()

        # Test initcheck api
        response = self.client.post(
            f"/api/v1.0/device_initcheck/{mlag_replacement_id}",
            json={"hostname": "mlag-a1", "device_type": "ACCESS", "replace_hostname": True},
        )
        self.assertEqual(response.status_code, 400)

        self.assertEqual(response.json.get("message"), "Replacing a MLAG switch is not supported")

        with self.assertRaises(DeviceError) as context:
            init_func(device_id=mlag_replacement_id, new_hostname="mlag-a1", replace_hostname=True)

        self.assertEqual("Replacing a MLAG switch is not supported", str(context.exception))

    @patch("cnaas_nms.devicehandler.init_device.pre_init_checks")
    def test_init_access_stack_error(
        self,
        mock_pre_init,
    ):
        """Test that when trying to replace a stacked switch it raises an exception"""

        def mocked_pre_init(session, device_id: int) -> Device:
            dev: Device = session.query(Device).filter(Device.id == device_id).one_or_none()
            return dev

        mock_pre_init.side_effect = mocked_pre_init

        init_func = cnaas_nms.devicehandler.init_device.init_access_device_step1.__wrapped__

        # Prepare test data.
        with sqla_session() as session:  # type: ignore
            stack_a1 = Device(
                hostname="stack-a1",
                platform="ios",
                state=DeviceState.UNMANAGED,  # UNMANAGED
                device_type=DeviceType.ACCESS,
            )
            stack_replacement = Device(
                management_ip=None,
                hostname="stack-replacement",
                platform="ios",
                state=DeviceState.DISCOVERED,
                device_type=DeviceType.UNKNOWN,
            )
            session.add(stack_a1)
            session.add(stack_replacement)
            session.commit()
            session.refresh(stack_a1)
            session.refresh(stack_replacement)

            stack_replacement_id = stack_replacement.id

            # Add stack member
            session.add(Stackmember(device_id=stack_a1.id, hardware_id="00:11:22:33:44:55", member_no=1, priority=10))
            session.commit()

        # Test initcheck api
        response = self.client.post(
            f"/api/v1.0/device_initcheck/{stack_replacement_id}",
            json={"hostname": "stack-a1", "device_type": "ACCESS", "replace_hostname": True},
        )
        self.assertEqual(response.status_code, 400)

        self.assertEqual(response.json.get("message"), "Replacing a stacked switch is not supported")

        with self.assertRaises(DeviceError) as context:
            init_func(device_id=stack_replacement_id, new_hostname="stack-a1", replace_hostname=True)

        self.assertEqual("Replacing a stacked switch is not supported", str(context.exception))

    @patch("cnaas_nms.devicehandler.update.get_interfaces_names")
    def test_init_access_uplink_removed(self, mock_get_interfaces_names):
        """
        Test that when replacing a switch with another switch with other uplink ports the original uplink ports are removed
        """

        # Override nornir get_interfaces
        mock_get_interfaces_names.return_value = ["Ethernet25"]

        # Prepare test data.
        with sqla_session() as session:  # type: ignore
            uplink_dev = Device(
                hostname="uplink-a2",
                platform="eos",
                state=DeviceState.MANAGED,
                device_type=DeviceType.ACCESS,
            )
            dev = Device(
                hostname="replaced-switch-with-orphaned-uplink",
                platform="eos",
                state=DeviceState.MANAGED,
                device_type=DeviceType.ACCESS,
            )

            session.add(uplink_dev)
            session.add(dev)
            session.commit()
            session.refresh(uplink_dev)
            session.refresh(dev)

            # Add Downlink ports to uplink_dev
            downlink_interface = Interface(
                device_id=uplink_dev.id, name="Ethernet1", configtype=InterfaceConfigType.ACCESS_DOWNLINK
            )
            session.add(downlink_interface)

            # Add orphaned uplink port
            # Interfaces
            interface = Interface(
                device_id=dev.id,
                name="TenGigabitEthernet1/1/1",  # Orphaned port
                configtype=InterfaceConfigType.ACCESS_UPLINK,
            )
            session.add(interface)
            session.commit()

            # New uplink port will be part of this linknets
            linknets = [
                {
                    "device_a_id": dev.id,
                    "device_a_port": "Ethernet25",
                    "device_b_id": uplink_dev.id,
                    "device_b_port": "Ethernet1",
                }
            ]

            update_interfacedb_worker(
                session, dev, replace=True, delete_all=False, linknets=linknets, replacing_device=True
            )

            interfaces = list(session.query(Interface).filter(Interface.device_id == dev.id))

            self.assertEqual(1, len(interfaces))

            self.assertEqual("Ethernet25", interfaces[0].name)
            self.assertEqual(InterfaceConfigType.ACCESS_UPLINK, interfaces[0].configtype)


if __name__ == "__main__":
    unittest.main()
