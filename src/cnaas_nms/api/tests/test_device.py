import json
import os
import unittest
from ipaddress import IPv4Address
from pathlib import Path

import pytest
from sqlalchemy import or_

from cnaas_nms.api import app
from cnaas_nms.api.tests.app_wrapper import TestAppWrapper
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.stackmember import Stackmember
from cnaas_nms.tools.yaml import yaml_safe_load


@pytest.mark.integration
@pytest.mark.usefixtures("mock_get_settings")
class DeviceTests(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def requirements(self, postgresql, settings_directory, mock_get_settings):
        """Ensures the required pytest fixtures are loaded implicitly for all these tests"""
        self.mock_get_settings = mock_get_settings

    def cleandb(self):
        with sqla_session() as session:  # type: ignore
            for hardware_id in ["AB1234", "CD5555", "GF43534"]:
                stack = session.query(Stackmember).filter(Stackmember.hardware_id == hardware_id).one_or_none()
                if stack:
                    session.delete(stack)
                    session.commit()
            for hostname in [
                "testdevice",
                "testdevice2",
                "testgroup-device1",
                "testfwdevice",
                "neighbor-device",
                "renamed-device",
                "hostname-device2",
                "test-dist1",
                "test-dist2",
                "access-old-name",
                "access-new-name",
            ]:
                device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
                if device:
                    session.query(Linknet).filter(
                        or_(Linknet.device_a_id == device.id, Linknet.device_b_id == device.id)
                    ).delete()
                    session.query(Interface).filter(Interface.device_id == device.id).delete()
                    session.delete(device)
                    session.commit()

    def setUp(self):
        self.jwt_auth_token = None
        data_dir = Path(__file__).parent / "data"
        with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
            self.testdata = yaml_safe_load(f_testdata)
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
        with sqla_session() as session:  # type: ignore
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

    def test_add_new_fw_device(self):
        device_data = {
            "hostname": "testfwdevice",
            "management_ip": "10.1.3.4",
            "dhcp_ip": "11.1.3.4",
            "ztp_mac": "0800275C0999",
            "platform": "junos",
            "state": "MANAGED",
            "device_type": "FIREWALL",
        }
        result = self.client.post("/api/v1.0/device", json=device_data)
        self.assertEqual(result.status_code, 200)

    def test_add_device_unsupported_platform_error(self):
        device_data = {
            "hostname": "testpanosaccess",
            "management_ip": "10.1.3.5",  # noqa: S1313
            "dhcp_ip": "11.1.3.5",  # noqa: S1313
            "ztp_mac": "0800275C0999",
            "platform": "panos",
            "state": "MANAGED",
            "device_type": "ACCESS",
        }
        result = self.client.post("/api/v1.0/device", json=device_data)
        self.assertEqual(result.status_code, 400)

    def test_add_device_no_platform(self):
        device_data = {
            "hostname": "testnoaccess",
            "management_ip": "10.1.3.6",  # noqa: S1313
            "dhcp_ip": "11.1.3.6",  # noqa: S1313
            "ztp_mac": "0800275C0999",
            "state": "MANAGED",
            "device_type": "ACCESS",
        }
        result = self.client.post("/api/v1.0/device", json=device_data)
        self.assertEqual(result.status_code, 400)

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
        with sqla_session() as session:  # type: ignore
            q_device = session.query(Device).filter(Device.hostname == self.hostname).one_or_none()
            self.assertEqual(modify_data["description"], q_device.description)

    def test_interface_data_mutable(self):
        from cnaas_nms.db.interface import Interface, InterfaceConfigType

        with sqla_session() as session:
            intf = Interface(
                device_id=self.device_id,
                name="test-intf",
                configtype=InterfaceConfigType.ACCESS_AUTO,
                data={"neighbor": "should-change"},
            )
            session.add(intf)
            session.commit()

            # Mutate JSONB field
            intf.data["neighbor"] = "changed"
            session.commit()

            # Verify mutation persisted
            updated = session.query(Interface).filter_by(name="test-intf", device_id=self.device_id).one()
            assert updated.data["neighbor"] == "changed"

            if updated:
                session.delete(updated)
                session.commit()

    def test_interface_export(self):
        from cnaas_nms.db.interface import Interface, InterfaceConfigType

        with sqla_session() as session:
            intf1 = Interface(
                device_id=self.device_id,
                name="Ethernet1",
                configtype=InterfaceConfigType.ACCESS_AUTO,
                data={"description": "testdesc"},
            )
            session.add(intf1)
            intf2 = Interface(
                device_id=self.device_id,
                name="Ethernet2",
                configtype=InterfaceConfigType.ACCESS_UPLINK,
                data={"neighbor": "testneigh"},
            )
            session.add(intf2)
            intf3 = Interface(
                device_id=self.device_id,
                name="Ethernet3",
                configtype=InterfaceConfigType.ACCESS_DOWNLINK,
            )
            session.add(intf3)
            session.commit()

            # Make a query with most things excluded
            response = self.client.get(
                f"/api/v1.0/device/{self.hostname}/interfaces_export",
                query_string={"include_downlinks": False, "include_descriptions": False},
            )
            # example output: {'interfaces': {'Ethernet1': {'configtype': 'ACCESS_AUTO', 'data': {'description': 'testdesc'}}}}
            for interface in response.json["interfaces"]:
                self.assertNotEqual(response.json["interfaces"][interface]["configtype"], "ACCESS_UPLINK")
            for interface in response.json["interfaces"]:
                self.assertNotEqual(response.json["interfaces"][interface]["configtype"], "ACCESS_DOWNLINK")
            for interface in response.json["interfaces"]:
                self.assertNotIn("description", response.json["interfaces"][interface]["data"])

            # Make a query with everything included
            response = self.client.get(
                f"/api/v1.0/device/{self.hostname}/interfaces_export",
                query_string={"include_uplinks": True},
            )
            for interface in response.json["interfaces"]:
                self.assertIn(interface, ["Ethernet1", "Ethernet2", "Ethernet3"])
            self.assertIn("description", response.json["interfaces"]["Ethernet1"]["data"])

            session.delete(intf1)
            session.delete(intf2)
            session.delete(intf3)
            session.commit()

    def test_rename_device_updates_neighbor(self):
        with sqla_session() as session:
            neighbor_device = Device(
                hostname="neighbor-device",
                platform="eos",
                management_ip=IPv4Address("10.2.2.2"),
                state=DeviceState.MANAGED,
                device_type=DeviceType.DIST,
                synchronized=True,
            )
            session.add(neighbor_device)
            session.commit()
            intf = Interface(
                device=neighbor_device,
                name="Ethernet1",
                configtype=InterfaceConfigType.ACCESS_AUTO,
                data={"neighbor": "testdevice"},
            )
            session.add(intf)
            session.commit()

        # Rename 'testdevice' to 'renamed-device'
        rename_data = {"hostname": "renamed-device"}
        rename_response = self.client.put(f"/api/v1.0/device/{self.device_id}", json=rename_data)
        assert rename_response.status_code == 200

        # Confirm that the neighbor field in interface has been updated
        with sqla_session() as session:
            renamed_device = session.query(Device).filter_by(hostname="renamed-device").one()
            assert renamed_device
            assert not renamed_device.synchronized
            assert session.query(Device).filter_by(hostname="testdevice").one_or_none() is None
            neighbor = session.query(Device).filter_by(hostname="neighbor-device").one()
            intf = session.query(Interface).filter_by(name="Ethernet1", device_id=neighbor.id).one()
            assert intf.data["neighbor"] == "renamed-device"
            assert not neighbor.synchronized

            # clean up
            session.delete(intf)
            session.delete(renamed_device)
            session.commit()

    def test_rename_device_marks_linknet_neighbors_unsync(self):
        """Test that renaming a device marks physically connected neighbors as unsynchronized via linknets"""
        with sqla_session() as session:
            # Create two DIST devices (uplinks) - synchronized and with NO interface data
            # Note:  DIST devices have NO interface entries
            dist1 = Device(
                hostname="test-dist1",
                platform="eos",
                management_ip=IPv4Address("10.100.1.1"),
                state=DeviceState.MANAGED,
                device_type=DeviceType.DIST,
                synchronized=True,
            )
            session.add(dist1)

            dist2 = Device(
                hostname="test-dist2",
                platform="eos",
                management_ip=IPv4Address("10.100.1.2"),
                state=DeviceState.MANAGED,
                device_type=DeviceType.DIST,
                synchronized=True,
            )
            session.add(dist2)
            session.flush()
            dist1_id = dist1.id
            dist2_id = dist2.id

            # Create ACCESS device that will be renamed
            access = Device(
                hostname="access-old-name",
                platform="eos",
                management_ip=IPv4Address("10.100.2.1"),
                state=DeviceState.MANAGED,
                device_type=DeviceType.ACCESS,
                synchronized=True,
            )
            session.add(access)
            session.flush()
            access_id = access.id

            # Create linknets connecting ACCESS to both DIST devices
            linknet1 = Linknet(
                device_a_id=access_id,
                device_a_port="Ethernet17",
                device_b_id=dist1_id,
                device_b_port="Ethernet2",
            )
            session.add(linknet1)

            linknet2 = Linknet(
                device_a_id=access_id,
                device_a_port="Ethernet18",
                device_b_id=dist2_id,
                device_b_port="Ethernet2",
            )
            session.add(linknet2)

            # Create ACCESS_UPLINK interfaces on ACCESS device with neighbor data
            # (This mimics real scenario where ACCESS devices have uplink interface data)
            intf1 = Interface(
                device_id=access_id,
                name="Ethernet17",
                configtype=InterfaceConfigType.ACCESS_UPLINK,
                data={"neighbor": "test-dist1"},
            )
            session.add(intf1)

            intf2 = Interface(
                device_id=access_id,
                name="Ethernet18",
                configtype=InterfaceConfigType.ACCESS_UPLINK,
                data={"neighbor": "test-dist2"},
            )
            session.add(intf2)

            session.commit()

        # Verify initial state:  all devices are synchronized
        with sqla_session() as session:
            access_dev = session.query(Device).filter(Device.id == access_id).one()
            dist1_dev = session.query(Device).filter(Device.id == dist1_id).one()
            dist2_dev = session.query(Device).filter(Device.id == dist2_id).one()

            assert access_dev.synchronized, "ACCESS device should start synchronized"
            assert dist1_dev.synchronized, "DIST1 device should start synchronized"
            assert dist2_dev.synchronized, "DIST2 device should start synchronized"

        # Rename the ACCESS device
        rename_data = {"hostname": "access-new-name"}
        rename_response = self.client.put(f"/api/v1.0/device/{access_id}", json=rename_data)
        assert rename_response.status_code == 200

        # Verify renamed device is unsynchronized
        with sqla_session() as session:
            renamed_device = session.query(Device).filter(Device.id == access_id).one()
            assert renamed_device.hostname == "access-new-name"
            assert not renamed_device.synchronized, "Renamed device should be unsynchronized"

        # Verify DIST neighbors are marked as unsynchronized
        with sqla_session() as session:
            dist1_dev = session.query(Device).filter(Device.id == dist1_id).one()
            dist2_dev = session.query(Device).filter(Device.id == dist2_id).one()

            assert not dist1_dev.synchronized, "DIST1 neighbor should be unsynchronized after ACCESS rename"
            assert not dist2_dev.synchronized, "DIST2 neighbor should be unsynchronized after ACCESS rename"

        # Verify interface neighbor fields were updated
        with sqla_session() as session:
            intf1 = (
                session.query(Interface).filter(Interface.device_id == access_id, Interface.name == "Ethernet17").one()
            )
            intf2 = (
                session.query(Interface).filter(Interface.device_id == access_id, Interface.name == "Ethernet18").one()
            )

            assert intf1.data["neighbor"] == "test-dist1", "Interface neighbor field should be updated"
            assert intf2.data["neighbor"] == "test-dist2", "Interface neighbor field should be updated"

        # Cleanup
        with sqla_session() as session:
            session.query(Interface).filter(Interface.device_id == access_id).delete()
            session.query(Linknet).filter(
                or_(Linknet.device_a_id == access_id, Linknet.device_b_id == access_id)
            ).delete()
            session.query(Device).filter(Device.id.in_([access_id, dist1_id, dist2_id])).delete()
            session.commit()

    def test_delete_device(self):
        result = self.client.delete(f"/api/v1.0/device/{self.device_id}")
        self.assertEqual(result.status_code, 200)
        with sqla_session() as session:  # type: ignore
            q_device = session.query(Device).filter(Device.hostname == self.hostname).one_or_none()
            self.assertIsNone(q_device)

    def test_change_device_name(self):
        rename_data = {"hostname": "renamed-device"}
        rename_response = self.client.put(f"/api/v1.0/device/{self.device_id}", json=rename_data)
        assert rename_response.status_code == 200

    def test_change_device_name_groups_changed_abort(self):
        rename_data = {"hostname": "testgroup-device1"}
        rename_response = self.client.put(f"/api/v1.0/device/{self.device_id}", json=rename_data)
        assert rename_response.status_code == 400

    def test_change_device_name_groups_changed_allow(self):
        device_id = 0
        # Device that is NOT in MANAGED state
        with sqla_session() as session:  # type: ignore
            device = Device(
                hostname="hostname-device2",
                platform="eos",
                management_ip=IPv4Address("10.0.1.22"),
                state=DeviceState.UNMANAGED,
                device_type=DeviceType.DIST,
            )
            session.add(device)
            session.commit()
            device_id = device.id
        # Change to hostname in TEST_GROUP
        rename_data = {"hostname": "testgroup-device1"}
        rename_response = self.client.put(f"/api/v1.0/device/{device_id}", json=rename_data)
        assert rename_response.status_code == 200

    def test_change_device_name_abort(self):
        mock_settings_old = {
            "vxlans": {
                "student1": {
                    "vni": "100500",
                    "ipv4_gw": "10.200.1.1/24",
                }
            },
        }
        mock_settings_new = {
            "vxlans": {
                "student1": {
                    "vni": "100500",
                    "ipv4_gw": "10.200.1.2/24",
                }
            },
        }

        self.mock_get_settings("testdevice", mock_settings_old)
        self.mock_get_settings("renamed-device", mock_settings_new)

        rename_data = {"hostname": "renamed-device"}
        rename_response = self.client.put(f"/api/v1.0/device/{self.device_id}", json=rename_data)
        assert rename_response.status_code == 400

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
        result = self.client.get(f"/api/v1.0/device/{'nonexisting'}/stackmember")
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 404, msg=json_data)

    def test_get_stackmembers_no_stackmembers(self):
        result = self.client.get(f"/api/v1.0/device/{self.hostname}/stackmember")
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(json_data["data"]["stackmembers"], [])

    def test_get_stackmembers(self):
        with sqla_session() as session:  # type: ignore
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
        with sqla_session() as session:  # type: ignore
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
        with sqla_session() as session:  # type: ignore
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
        with sqla_session() as session:  # type: ignore
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

    @pytest.mark.equipment
    def test_get_lldp_neighbors(self):
        hostname = self.testdata["managed_dist"]
        result = self.client.get(f"/api/v1.0/device/{hostname}/lldp_neighbors")
        self.assertEqual(result.status_code, 200, "Get LLDP neighbors failed")

    @pytest.mark.equipment
    def test_get_lldp_neighbors_detail(self):
        hostname = self.testdata["managed_dist"]
        result = self.client.get(f"/api/v1.0/device/{hostname}/lldp_neighbors_detail")
        self.assertEqual(result.status_code, 200, "Get LLDP neighbors detail failed")


if __name__ == "__main__":
    unittest.main()
