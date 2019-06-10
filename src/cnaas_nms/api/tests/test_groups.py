import pprint
import shutil
import yaml
import pkg_resources
import os

import json
import unittest

from flask import request
from flask_restful import Resource

from cnaas_nms.api import app
from cnaas_nms.db.session import sqla_session, sqla_execute
from cnaas_nms.db.groups import Groups, DeviceGroups
from cnaas_nms.db.device import Device


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_1_add_new_group(self):
        Groups.add('group0', 'Unittest group')

    def test_2_get_group(self):
        result = Groups.get(name='group0')
        self.assertNotEquals(result, [])

    def test_4_add_device(self):
        device_data = {
            "hostname": "groupdevice",
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

    def test_5_add_device_to_group(self):
        device_id = 0
        result = self.client.get('/api/v1.0/device')
        json_data = json.loads(result.data.decode())
        for _ in json_data['data']['devices']:
            if _['hostname'] != 'groupdevice':
                continue
            device_id = _['id']
        self.assertIsNot(device_id, 0)
        groups = Groups.get(name='group0')
        group_id = groups[0]['id']
        DeviceGroups.add(group_id, device_id)
        xid = 0
        for _ in DeviceGroups.get(group_id):
            if _['id'] == device_id:
                xid = device_id
        self.assertEqual(device_id, xid)

    def test_6_delete_device_from_group(self):
        device_id = 0
        result = self.client.get('/api/v1.0/device')
        json_data = json.loads(result.data.decode())
        json_data = json.loads(result.data.decode())
        for _ in json_data['data']['devices']:
            if _['hostname'] != 'groupdevice':
                continue
            device_id = _['id']
        self.assertIsNot(device_id, 0)
        groups = Groups.get(name='group0')
        group_id = groups[0]['id']
        DeviceGroups.delete(group_id, device_id)

    def test_8_delete_group(self):
        groups = Groups.get(name='group0')
        group_id = groups[0]['id']
        Groups.delete(group_id)

    def test_9_delete_device(self):
        device_id = 0
        result = self.client.get('/api/v1.0/device')
        json_data = json.loads(result.data.decode())
        for _ in json_data['data']['devices']:
            if _['hostname'] != 'groupdevice':
                continue
            device_id = _['id']
        self.assertIsNot(device_id, 0)
        result = self.client.delete(f'/api/v1.0/device/{ device_id }')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')


if __name__ == '__main__':
    unittest.main()
