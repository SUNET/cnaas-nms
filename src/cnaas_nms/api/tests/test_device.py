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
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.stackmember import Stackmember


@pytest.mark.integration
class DeviceTests(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def requirements(self, postgresql, settings_directory):
        """Ensures the required pytest fixtures are loaded implicitly for all these tests"""
        pass

    def cleandb(self):
        with sqla_session() as session:
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
        self.hostname = hostname

    def tearDown(self):
        self.cleandb()

    def add_device(self):
        with sqla_session() as session:
            device = Device(
                hostname="testdevice",
                platform="eos",
                management_ip=IPv4Address("10.0.1.22"),
                state=DeviceState.MANAGED,
                device_type=DeviceType.DIST,
            )
            session.add(device)
            session.commit()
            return device.id, device.hostname

    def test_add_invalid_device(self):
        device_data = {
            "hostname": "testdevice2",
            "management_ip": "10.1.2.3",
            "dhcp_ip": "11.1.2.3",
            "ztp_mac": "0800275C091F",
            "platform": "eos",
            "state": "invalid_state",
            "device_type": "ACCESS",
        }
        result = self.client.post("/api/v1.0/device", json=device_data)
        self.assertEqual(result.status_code, 400)

    def test_add_new_device(self):
        device_data = {
            "hostname": "testdevice2",
            "management_ip": "10.1.2.3",
            "dhcp_ip": "11.1.2.3",
            "ztp_mac": "0800275C091F",
            "platform": "eos",
            "state": "MANAGED",
            "device_type": "DIST",
        }
        result = self.client.post("/api/v1.0/device", json=device_data)
        self.assertEqual(result.status_code, 200)

    def test_get_device(self):
        result = self.client.get(f"/api/v1.0/device/{self.hostname}")
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        self.assertEqual([self.hostname], [device["hostname"] for device in json_data["data"]["devices"]])

    def test_get_devices(self):
        result = self.client.get("/api/v1.0/devices")
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        self.assertTrue(self.hostname in [device["hostname"] for device in json_data["data"]["devices"]])

    def test_modify_device(self):
        modify_data = {"description": "changed_description"}
        result = self.client.put(f"/api/v1.0/device/{self.device_id}", json=modify_data)
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        updated_device = json_data["data"]["updated_device"]
        self.assertEqual(modify_data["description"], updated_device["description"])
        with sqla_session() as session:
            q_device = session.query(Device).filter(Device.hostname == self.hostname).one_or_none()
            self.assertEqual(modify_data["description"], q_device.description)

    def test_delete_device(self):
        result = self.client.delete(f"/api/v1.0/device/{self.device_id}")
        self.assertEqual(result.status_code, 200)
        with sqla_session() as session:
            q_device = session.query(Device).filter(Device.hostname == self.hostname).one_or_none()
            self.assertIsNone(q_device)

    @pytest.mark.equipment
    def test_initcheck_distdevice(self):
        device_id = self.testdata["initcheck_device_id"]
        pre_state = self.client.get(f"/api/v1.0/device/{device_id}").json["data"]["devices"][0]["state"]
        self.client.put(f"/api/v1.0/device/{device_id}", json={"state": "DISCOVERED"})
        device_data = {"hostname": "distcheck", "device_type": "DIST"}
        result = self.client.post(f"/api/v1.0/device_initcheck/{device_id}", json=device_data)
        self.client.put(f"/api/v1.0/device/{device_id}", json={"state": pre_state})
        self.assertEqual(result.status_code, 500)
        json_data = json.loads(result.data.decode())
        #        self.assertEqual(json_data['data']['compatible'], False)
        self.assertEqual(json_data["status"], "error")

    def test_get_stackmembers_invalid_device(self):
        result = self.client.get(f'/api/v1.0/device/{"nonexisting"}/stackmember')
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 404, msg=json_data)

    def test_get_stackmembers_no_stackmembers(self):
        result = self.client.get(f"/api/v1.0/device/{self.hostname}/stackmember")
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(json_data["data"]["stackmembers"], [])

    def test_get_stackmembers(self):
        with sqla_session() as session:
            stackmember = Stackmember(device_id=self.device_id, hardware_id="AB1234", member_no=1, priority=3)
            session.add(stackmember)
        result = self.client.get(f"/api/v1.0/device/{self.hostname}/stackmember")
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 200, msg=json_data)
        self.assertEqual(len(json_data["data"]["stackmembers"]), 1, msg=json_data)
        self.assertEqual(json_data["data"]["stackmembers"][0]["hardware_id"], "AB1234", msg=json_data)

    def test_put_stackmembers_valid(self):
        stackmember_data = {
            "stackmembers": [
                {"hardware_id": "AB1234", "member_no": 0, "priority": None},
                {"hardware_id": "CD5555", "member_no": 2, "priority": 99},
                {"hardware_id": "GF43534", "member_no": 5},
            ]
        }
        result = self.client.put(f"/api/v1.0/device/{self.hostname}/stackmember", json=stackmember_data)
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 200, msg=json_data)
        self.assertEqual(len(json_data["data"]["stackmembers"]), 3, msg=json_data)
        with sqla_session() as session:
            q_stackmembers = session.query(Stackmember).filter(Stackmember.device_id == self.device_id).all()
            self.assertEqual(len(q_stackmembers), 3, msg=json_data)

    def test_put_stackmembers_invalid_priority(self):
        stackmember_data = {"stackmembers": [{"hardware_id": "AB1234", "member_no": 1, "priority": "string"}]}
        result = self.client.put(f"/api/v1.0/device/{self.hostname}/stackmember", json=stackmember_data)
        self.assertEqual(result.status_code, 400)

    def test_put_stackmembers_invalid_member_no(self):
        stackmember_data = {"stackmembers": [{"hardware_id": "AB1234", "member_no": "string"}]}
        result = self.client.put(f"/api/v1.0/device/{self.hostname}/stackmember", json=stackmember_data)
        self.assertEqual(result.status_code, 400)

    def test_put_stackmembers_invalid_hardware_id(self):
        stackmember_data = {"stackmembers": [{"hardware_id": "", "member_no": 0}]}
        result = self.client.put(f"/api/v1.0/device/{self.hostname}/stackmember", json=stackmember_data)
        self.assertEqual(result.status_code, 400)

    def test_put_stackmembers_clear(self):
        with sqla_session() as session:
            stackmember = Stackmember(
                device_id=self.device_id,
                hardware_id="AB1234",
                member_no=1,
                priority=3,
            )
            session.add(stackmember)
        stackmember_data = {"stackmembers": []}
        result = self.client.put(f"/api/v1.0/device/{self.hostname}/stackmember", json=stackmember_data)
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(json_data["data"]["stackmembers"]), 0)
        with sqla_session() as session:
            q_stackmembers = session.query(Stackmember).filter(Stackmember.device_id == self.device_id).all()
            self.assertEqual(len(q_stackmembers), 0)

    def test_put_stackmembers_dupe_member_no(self):
        stackmember_data = {
            "stackmembers": [{"hardware_id": "DC1231", "member_no": 1}, {"hardware_id": "CD5555", "member_no": 1}]
        }
        result = self.client.put(f"/api/v1.0/device/{self.hostname}/stackmember", json=stackmember_data)
        self.assertEqual(result.status_code, 400)

    def test_put_stackmembers_dupe_hardware_id(self):
        stackmember_data = {
            "stackmembers": [{"hardware_id": "AA1111", "member_no": 1}, {"hardware_id": "AA1111", "member_no": 2}]
        }
        result = self.client.put(f"/api/v1.0/device/{self.hostname}/stackmember", json=stackmember_data)
        self.assertEqual(result.status_code, 400)

    def test_put_synchistory_event_valid(self):
        data = {
            "hostname": "eosaccess",
            "cause": "unittest_cause",
            "by": "unittest_user",
        }
        result = self.client.post("/api/v1.0/device_synchistory", json=data)
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 200, msg=json_data)
        self.assertEqual(len(json_data["data"].keys()), 4, msg=json_data)

    def test_put_synchistory_event_no_hostname(self):
        data = {
            "cause": "unittest_cause",
            "by": "unittest_user",
        }
        result = self.client.post("/api/v1.0/device_synchistory", json=data)
        self.assertEqual(result.status_code, 400)

    def test_put_synchistory_event_invalid_hostname(self):
        data = {
            "hostname": "devicethatdoesnotexist",
            "cause": "unittest_cause",
            "by": "unittest_user",
        }
        result = self.client.post("/api/v1.0/device_synchistory", json=data)
        self.assertEqual(result.status_code, 400)

    def test_put_synchistory_event_invalid_timestamp(self):
        data = {
            "cause": "unittest_cause",
            "by": "unittest_user",
            "timestamp": "2023",
        }
        result = self.client.post("/api/v1.0/device_synchistory", json=data)
        self.assertEqual(result.status_code, 400)

    def test_get_synchistory(self):
        result = self.client.get("/api/v1.0/device_synchistory", query_string={"hostname": "eosaccess"})
        self.assertEqual(result.status_code, 200, "Get synchistory for single device failed")
        self.assertTrue("data" in result.json)
        result = self.client.get("/api/v1.0/device_synchistory")
        self.assertEqual(result.status_code, 200, "Get synchistory for all devices failed")
        self.assertTrue("data" in result.json)

    @pytest.mark.equipment
    def test_get_running_config(self):
        hostname = self.testdata["managed_dist"]
        result = self.client.get(f"/api/v1.0/device/{hostname}/running_config")
        self.assertEqual(result.status_code, 200, "Get running config failed")

    @pytest.mark.equipment
    def test_get_running_config_interface(self):
        hostname = self.testdata["managed_dist"]
        result = self.client.get(f"/api/v1.0/device/{hostname}/running_config", query_string={"interface": "Ethernet1"})
        self.assertEqual(result.status_code, 200, "Get running config interface failed")


if __name__ == "__main__":
    unittest.main()
