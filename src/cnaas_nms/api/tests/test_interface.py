import json
import os
import unittest
from ipaddress import IPv4Address

import pkg_resources
import pytest
import yaml

from cnaas_nms.api import app
from cnaas_nms.api.tests.app_wrapper import TestAppWrapper
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.stackmember import Stackmember


@pytest.mark.integration
class InterfaceTests(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def requirements(self, postgresql, settings_directory):
        """Ensures the required pytest fixtures are loaded implicitly for all these tests"""
        pass

    def cleandb(self):
        with sqla_session() as session:  # type: ignore
            for hardware_id in ["AB1234", "CD5555", "GF43534"]:
                stack = session.query(Stackmember).filter(Stackmember.hardware_id == hardware_id).one_or_none()
                if stack:
                    session.delete(stack)
                    session.commit()
            for hostname in ["testdevice", "testdevice2"]:
                device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
                if device:
                    session.delete(device)
                    session.commit()

    def setUp(self):
        self.jwt_auth_token = None
        data_dir = pkg_resources.resource_filename(__name__, "data")
        with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)
            if "jwt_auth_token" in self.testdata:
                self.jwt_auth_token = self.testdata["jwt_auth_token"]
        self.app = app.app
        self.app.wsgi_app = TestAppWrapper(self.app.wsgi_app, self.jwt_auth_token)
        self.client = self.app.test_client()
        self.cleandb()
        device_id, hostname = self.add_device()
        self.device_id = device_id
        self.device_hostname = hostname
        self.add_interfaces(device_id)

    def tearDown(self):
        self.cleandb()

    def add_device(self):
        with sqla_session() as session:  # type: ignore
            device = Device(
                hostname="testdevice",
                platform="eos",
                management_ip=IPv4Address("10.0.1.22"),
                state=DeviceState.MANAGED,
                device_type=DeviceType.ACCESS,
            )
            session.add(device)
            session.commit()
            return device.id, device.hostname

    def add_interfaces(self, device_id):
        with sqla_session() as session:  # type: ignore
            interface = Interface(
                name="testinterface1",
                configtype=InterfaceConfigType.ACCESS_AUTO,
                data={
                    "patch_position": "3E-H12",
                },
                device_id=device_id,
            )
            interface2 = Interface(
                name="testinterface2",
                configtype=InterfaceConfigType.ACCESS_AUTO,
                data={},
                device_id=device_id,
            )
            session.add(interface)
            session.add(interface2)
            session.commit()

    def test_get_interface(self):
        result = self.client.get(f"/api/v1.0/device/{self.device_hostname}/interfaces")
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        self.assertEqual(
            ["testinterface1", "testinterface2"], [interface["name"] for interface in json_data["data"]["interfaces"]]
        )

    def test_update_interface_not_unique(self):
        modify_data = {
            "interfaces": {
                "testinterface1": {
                    "data": {
                        "description": "new description",
                    }
                },
                "testinterface2": {
                    "data": {
                        "patch_position": "3E-H12",
                    }
                },
            }
        }
        result = self.client.put(f"/api/v1.0/device/{self.device_hostname}/interfaces", json=modify_data)
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 400)
        self.assertEqual(json_data["status"], "error")

    def test_update_interface(self):
        modify_data = {
            "interfaces": {
                "testinterface1": {
                    "data": {
                        "description": "test",
                    }
                },
                "testinterface2": {
                    "data": {
                        "description": "test",
                        "patch_position": "XW.H4.23",
                    }
                },
            }
        }
        result = self.client.put(f"/api/v1.0/device/{self.device_hostname}/interfaces", json=modify_data)
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(["testinterface1", "testinterface2"], list(json_data["data"]["updated"].keys()))


if __name__ == "__main__":
    unittest.main()
