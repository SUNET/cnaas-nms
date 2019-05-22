import yaml
import pkg_resources
import os
import json

import unittest

from cnaas_nms.api import app
from cnaas_nms.tools.testsetup import PostgresTemporaryInstance
from cnaas_nms.tools.testsetup import MongoTemporaryInstance


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        self.tmp_postgres = PostgresTemporaryInstance()
        self.tmp_mongo = MongoTemporaryInstance()
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)

    def tearDown(self):
        self.tmp_postgres.shutdown()
        self.tmp_mongo.shutdown()

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
        self.assertEqual(result.status_code, 404)

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
            "device_type": "ACCESS",
        }
        result = self.client.post('/api/v1.0/device', json=device_data)
        self.assertEqual(result.status_code, 200)

    def test_2_get_device(self):
        device_id = 0
        result = self.client.get('/api/v1.0/device')
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        for _ in json_data:
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
        result = self.client.get('/api/v1.0/device')
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        for _ in json_data:
            if _['hostname'] != 'unittestdevice':
                continue
            device_id = _['id']
        self.assertIsNot(device_id, 0)
        result = self.client.put(f'/api/v1.0/device/{device_id}', json=device_data)
        self.assertEqual(result.status_code, 200)

    def test_4_delete_device(self):
        device_id = 0
        result = self.client.get('/api/v1.0/device')
        self.assertEqual(result.status_code, 200)
        json_data = json.loads(result.data.decode())
        for _ in json_data:
            if _['hostname'] != 'unittestdevicechanged':
                continue
            device_id = _['id']
        self.assertIsNot(device_id, 0)
        result = self.client.delete(f'/api/v1.0/device/{device_id}')
        self.assertEqual(result.status_code, 200)
