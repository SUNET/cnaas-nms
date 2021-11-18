import yaml
import pkg_resources
import os
import json

import unittest

from cnaas_nms.api import app
from cnaas_nms.tools.testsetup import PostgresTemporaryInstance
from cnaas_nms.db.session import clear_db
from cnaas_nms.api.tests.app_wrapper import TestAppWrapper


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.jwt_auth_token = None
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)
            if 'jwt_auth_token' in self.testdata:
                self.jwt_auth_token = self.testdata['jwt_auth_token']
        self.app = app.app
        self.app.wsgi_app = TestAppWrapper(self.app.wsgi_app, self.jwt_auth_token)
        self.client = self.app.test_client()
        self.tmp_postgres = PostgresTemporaryInstance()

    def tearDown(self):
        device_id = self.testdata['initcheck_device_id']
        self.client.put(f'/api/v1.0/device/{device_id}',
                        json={'state': 'MANAGED'})
        self.tmp_postgres.shutdown()
        clear_db()

    def test_0_add_invalid_device(self):
        device_data = {
            "hostname": "unittestdevice",
            "site_id": 1,
            "description": '',
            "management_ip": "10.1.2.3",
            "dhcp_ip": "11.1.2.3",
            "serial": '',
            "ztp_mac": "0800275C091F",
            "platform": "eos",
            "vendor": '',
            "model": '',
            "os_version": '',
            "state": "blah",
            "device_type": "ACCESS",
        }
        result = self.client.post('/api/v1.0/device', json=device_data)
        self.assertEqual(result.status_code, 400)

    def test_1_add_new_device(self):
        device_data = {
            "hostname": "unittestdevice",
            "site_id": 1,
            "description": '',
            "management_ip": "10.1.2.3",
            "dhcp_ip": "11.1.2.3",
            "serial": '',
            "ztp_mac": "0800275C091F",
            "platform": "eos",
            "vendor": '',
            "model": '',
            "os_version": '',
            "state": "MANAGED",
            "device_type": "DIST",
        }
        result = self.client.post('/api/v1.0/device', json=device_data)
        self.assertEqual(result.status_code, 200)

    def test_2_get_device(self):
        device_id = 0
        result = self.client.get('/api/v1.0/devices')
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        for _ in json_data['data']['devices']:
            if _['hostname'] != 'unittestdevice':
                continue
            device_id = _['id']
        self.assertIsNot(device_id, 0)
        result = self.client.get(f'/api/v1.0/device/{device_id}')
        self.assertEqual(result.status_code, 200)

    def test_3_modify_device(self):
        device_data = {
            "hostname": "unittestdevicechanged",
            "site_id": 1,
            "description": '',
            "management_ip": "10.10.10.10",
            "dhcp_ip": "11.11.11.11",
            "serial": '',
            "ztp_mac": "0800275C091F",
            "platform": "eos",
            "vendor": '',
            "model": '',
            "os_version": '',
            "state": "MANAGED",
            "device_type": "ACCESS",
        }
        device_id = 0
        result = self.client.get('/api/v1.0/devices')
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        for _ in json_data['data']['devices']:
            if _['hostname'] != 'unittestdevice':
                continue
            device_id = _['id']
        self.assertIsNot(device_id, 0)
        result = self.client.put(f'/api/v1.0/device/{device_id}',
                                 json=device_data)
        self.assertEqual(result.status_code, 200)
        result = self.client.get(f'/api/v1.0/device/{device_id}')
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        json_data = json_data['data']['devices'][0]
        self.assertIsNot(json_data['hostname'], '')
        self.assertIsNot(json_data['site_id'], '')
        self.assertIsNot(json_data['management_ip'], '')
        self.assertIsNot(json_data['dhcp_ip'], None)
        self.assertIsNot(json_data['ztp_mac'], '')
        self.assertIsNot(json_data['platform'], '')
        self.assertIsNot(json_data['state'], '')
        self.assertIsNot(json_data['device_type'], '')

    def test_4_delete_device(self):
        device_id = 0
        result = self.client.get('/api/v1.0/devices')
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        for _ in json_data['data']['devices']:
            if _['hostname'] != 'unittestdevicechanged':
                continue
            device_id = _['id']
        self.assertIsNot(device_id, 0)
        result = self.client.delete(f'/api/v1.0/device/{device_id}')
        self.assertEqual(result.status_code, 200)

    def test_5_initcheck_distdevice(self):
        device_id = self.testdata['initcheck_device_id']
        self.client.put(f'/api/v1.0/device/{device_id}',
                        json={'state': 'DISCOVERED'})

        device_data = {
            "hostname": "distcheck",
            "device_type": "DIST"
        }
        result = self.client.post(f'/api/v1.0/device_initcheck/{device_id}',
                                  json=device_data)
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        self.assertEqual(json_data['data']['compatible'], False)

        self.client.put(f'/api/v1.0/device/{device_id}',
                        json={'state': 'MANAGED'})


if __name__ == '__main__':
    unittest.main()
