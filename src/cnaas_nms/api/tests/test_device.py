import yaml
import pkg_resources
import os
import json
import unittest
from ipaddress import IPv4Address

from cnaas_nms.api import app
from cnaas_nms.db.session import clear_db, sqla_session
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.stackmember import Stackmember
from cnaas_nms.api.tests.app_wrapper import TestAppWrapper


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.jwt_auth_token = None
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)
            if 'jwt_auth_token' in self.testdata:
                self.jwt_auth_token = self.testdata['jwt_auth_token']
        os.environ["USERNAME_DHCP_BOOT"] = "cnaas"
        os.environ["PASSWORD_DHCP_BOOT"] = "cnaas"
        os.environ["USERNAME_DISCOVERED"] = "cnaas"
        os.environ["PASSWORD_DISCOVERED"] = "cnaas"
        os.environ["USERNAME_INIT"] = "cnaas"
        os.environ["PASSWORD_INIT"] = "cnaas"
        os.environ["USERNAME_MANAGED"] = "cnaas"
        os.environ["PASSWORD_MANAGED"] = "cnaas"
        self.app = app.app
        self.app.wsgi_app = TestAppWrapper(self.app.wsgi_app, self.jwt_auth_token)
        self.client = self.app.test_client()

    def tearDown(self):
        clear_db()

    def create_test_device(self, device_id=1):
        return Device(
            id=device_id,
            ztp_mac="08002708a8be",
            hostname="unittest",
            platform="eos",
            management_ip=IPv4Address("10.0.1.22"),
            state=DeviceState.MANAGED,
            device_type=DeviceType.DIST,
        )

    def test_add_invalid_device(self):
        device_data = {
            "hostname": "unittestdevice",
            "management_ip": "10.1.2.3",
            "dhcp_ip": "11.1.2.3",
            "ztp_mac": "0800275C091F",
            "platform": "eos",
            "state": "invalid_state",
            "device_type": "ACCESS",
        }
        result = self.client.post('/api/v1.0/device', json=device_data)
        self.assertEqual(result.status_code, 400)

    def test_add_new_device(self):
        device_data = {
            "hostname": "unittestdevice",
            "management_ip": "10.1.2.3",
            "dhcp_ip": "11.1.2.3",
            "ztp_mac": "0800275C091F",
            "platform": "eos",
            "state": "MANAGED",
            "device_type": "DIST",
        }
        result = self.client.post('/api/v1.0/device', json=device_data)
        self.assertEqual(result.status_code, 200)

    def test_get_device(self):
        new_device = self.create_test_device(1)
        with sqla_session() as session:
            session.add(new_device)
        result = self.client.get('/api/v1.0/devices')
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        self.assertEqual([1], [device['id'] for device in json_data['data']['devices']])
        result = self.client.get(f'/api/v1.0/device/{1}')
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        self.assertEqual([1], [device['id'] for device in json_data['data']['devices']])

    def test_modify_device(self):
        device_data = {"hostname": "unittestdevicechanged"}
        new_device = self.create_test_device(device_id=1)
        with sqla_session() as session:
            session.add(new_device)
        result = self.client.put(f'/api/v1.0/device/{1}', json=device_data)
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        updated_device = json_data['data']['updated_device']
        self.assertEqual(device_data['hostname'], updated_device['hostname'])
        with sqla_session() as session:
            q_device = session.query(Device).filter(Device.id == 1).one_or_none()
            self.assertEqual(device_data['hostname'], q_device.hostname)

    def test_delete_device(self):
        new_device = self.create_test_device(device_id=1)
        with sqla_session() as session:
            session.add(new_device)
        result = self.client.delete(f'/api/v1.0/device/{1}')
        self.assertEqual(result.status_code, 200)
        with sqla_session() as session:
            q_device = session.query(Device).filter(Device.id == 1).one_or_none()
            self.assertIsNone(q_device)

    def test_initcheck_distdevice(self):
        device_id = self.testdata['initcheck_device_id']
        self.client.put(f'/api/v1.0/device/{device_id}', json={'state': 'DISCOVERED'})
        device_data = {"hostname": "distcheck", "device_type": "DIST"}
        result = self.client.post(f'/api/v1.0/device_initcheck/{device_id}', json=device_data)
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        self.assertEqual(json_data['data']['compatible'], False)

    def test_get_stackmembers_invalid_device(self):
        result = self.client.get(f'/api/v1.0/device/{1}/stackmember')
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 404, msg=json_data)

    def test_get_stackmembers_no_stackmembers(self):
        new_device = self.create_test_device(device_id=1)
        with sqla_session() as session:
            session.add(new_device)
        result = self.client.get(f'/api/v1.0/device/{1}/stackmember')
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 200, msg=json_data)
        self.assertEqual(json_data['data']['stackmembers'], [], msg=json_data)

    def test_get_stackmembers(self):
        new_device = self.create_test_device(device_id=1)
        with sqla_session() as session:
            session.add(new_device)
            stackmember = Stackmember(device_id=1, hardware_id="AB1234", member_no=1, priority=3)
            session.add(stackmember)
        result = self.client.get(f'/api/v1.0/device/{1}/stackmember')
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 200, msg=json_data)
        self.assertEqual(len(json_data['data']['stackmembers']), 1, msg=json_data)
        self.assertEqual(json_data['data']['stackmembers'][0]["hardware_id"], "AB1234", msg=json_data)

    def test_put_stackmembers_valid(self):
        new_device = self.create_test_device(device_id=1)
        with sqla_session() as session:
            session.add(new_device)
        stackmember_data = {'stackmembers': [
            {"hardware_id": "AB1234", "member_no": 0, "priority": None},
            {"hardware_id": "CD5555", "member_no": 2, "priority": 99},
            {"hardware_id": "GF43534", "member_no": 5},
        ]}
        result = self.client.put(f'/api/v1.0/device/{1}/stackmember', json=stackmember_data)
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 200, msg=json_data)
        self.assertEqual(len(json_data['data']['stackmembers']), 3, msg=json_data)
        with sqla_session() as session:
            q_stackmembers = session.query(Stackmember).filter(Stackmember.device_id == 1).all()
            self.assertEqual(len(q_stackmembers), 3, msg=json_data)
    
    def test_put_stackmembers_invalid_member_no(self):
        new_device = self.create_test_device(device_id=1)
        with sqla_session() as session:
            session.add(new_device)
        stackmember_data = {'stackmembers': [
            {"hardware_id": "AB1234", "member_no": "string"}]}
        result = self.client.put(f'/api/v1.0/device/{1}/stackmember', json=stackmember_data)
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 400, msg=json_data)
        with sqla_session() as session:
            q_stackmembers = session.query(Stackmember).filter(Stackmember.device_id == 1).all()
            self.assertEqual(q_stackmembers, [])

    def test_put_stackmembers_invalid_hardware_id(self):
        new_device = self.create_test_device(device_id=1)
        with sqla_session() as session:
            session.add(new_device)
        stackmember_data = {'stackmembers': [{"hardware_id": "", "member_no": 0}]}
        result = self.client.put(f'/api/v1.0/device/{1}/stackmember', json=stackmember_data)
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 400, msg=json_data)
        with sqla_session() as session:
            q_stackmembers = session.query(Stackmember).filter(Stackmember.device_id == 1).all()
            self.assertEqual(q_stackmembers, [])

    def test_put_stackmembers_clear(self):
        new_device = self.create_test_device(device_id=1)
        with sqla_session() as session:
            session.add(new_device)
            stackmember = Stackmember(device_id=1, hardware_id="AB1234", member_no=1, priority=3,)
            session.add(stackmember)
        stackmember_data = {'stackmembers': []}
        result = self.client.put(f'/api/v1.0/device/{1}/stackmember', json=stackmember_data)
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 200, msg=json_data)
        self.assertEqual(len(json_data['data']['stackmembers']), 0, msg=json_data)
        with sqla_session() as session:
            q_stackmembers = session.query(Stackmember).filter(Stackmember.device_id == 1).all()
            self.assertEqual(len(q_stackmembers), 0, msg=json_data)     
    
    def test_put_stackmembers_dupe_member_no(self):
        new_device = self.create_test_device(device_id=1)
        with sqla_session() as session:
            session.add(new_device)
            stackmember = Stackmember(device_id=1, hardware_id="AB1234", member_no=1, priority=3)
            session.add(stackmember)
        stackmember_data = {'stackmembers': [
            {"hardware_id": "DC1231", "member_no": 1},
            {"hardware_id": "CD5555", "member_no": 1}
        ]}
        result = self.client.put(f'/api/v1.0/device/{1}/stackmember', json=stackmember_data)
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 400, msg=json_data)
    
    def test_put_stackmembers_dupe_hardware_id(self):
        new_device = self.create_test_device(device_id=1)
        with sqla_session() as session:
            session.add(new_device)
            stackmember = Stackmember(device_id=1, hardware_id="AB1234", member_no=1, priority=3)
            session.add(stackmember)
        stackmember_data = {'stackmembers': [
            {"hardware_id": "AA1111", "member_no": 1},
            {"hardware_id": "AA1111", "member_no": 2}
        ]}
        result = self.client.put(f'/api/v1.0/device/{1}/stackmember', json=stackmember_data)
        json_data = json.loads(result.data.decode())
        self.assertEqual(result.status_code, 400, msg=json_data)

if __name__ == '__main__':
    unittest.main()
