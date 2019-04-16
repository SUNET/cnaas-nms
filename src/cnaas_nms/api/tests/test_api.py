import pprint
import shutil
import yaml

import unittest

import cnaas_nms.api

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = cnaas_nms.api.app.test_client()

    def test_get_single_device(self):
        device_id = 1
        result = self.client.get(f'/api/v1.0/device/{device_id}')

        pprint.pprint(result.json)

        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Succes in json
        self.assertEqual(result.json['status'], 'success')
        # Exactly one result
        self.assertEqual(len(result.json['data']['devices']), 1)
        # The one result should have the same ID we asked for
        self.assertEqual(result.json['data']['devices'][0]['id'], device_id)

    def test_get_last_job(self):
        result = self.client.get('/api/v1.0/job?limit=1')

        pprint.pprint(result.json)

        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Succes in json
        self.assertEqual(result.json['status'], 'success')
        # Exactly one result
        self.assertEqual(len(result.json['data']['jobs']), 1)

    def test_get_managementdomain(self):
        result = self.client.get('/api/v1.0/mgmtdomain?limit=1')
        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Succes in json
        self.assertEqual(result.json['status'], 'success')
        # Exactly one result
        self.assertEqual(len(result.json['data']['mgmtdomains']), 1)
        # The one result should have the same ID we asked for
        self.assertIsInstance(result.json['data']['mgmtdomains'][0]['id'], int)

    def test_repository_refresh(self):
        data = {"action": "refresh"}
        result = self.client.put('/api/v1.0/repository/settings', json=data)
        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Succes in json
        self.assertEqual(result.json['status'], 'success')
        # Exactly one result
        self.assertRegex(result.json['data'], r'[Cc]ommit')

    def test_repository_get(self):
        # Delete settings repo
        with open('/etc/cnaas-nms/repository.yml', 'r') as db_file:
            repo_config = yaml.safe_load(db_file)
        shutil.rmtree(repo_config['settings_local'])

        # Check that no repo is found
        result = self.client.get('/api/v1.0/repository/settings')
        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Succes in json
        self.assertEqual(result.json['status'], 'success')
        # Exactly one result
        self.assertEqual(result.json['data'], "Repository is not yet cloned from remote")

        # Refresh repo
        self.test_repository_refresh()

        # Check that repo has a commit after the refresh
        result = self.client.get('/api/v1.0/repository/settings')
        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Succes in json
        self.assertEqual(result.json['status'], 'success')
        # Exactly one result
        self.assertRegex(result.json['data'], r'[Cc]ommit')

    def test_sync_devices_invalid_input(self):
        # Test invalid hostname
        data = {"hostname": "...", "dry_run": True}
        result = self.client.post('/api/v1.0/device_sync', json=data)
        self.assertEqual(result.status_code, 400)

        # Test invalid device_type
        data = {"device_type": "nonexistent", "dry_run": True}
        result = self.client.post('/api/v1.0/device_sync', json=data)
        self.assertEqual(result.status_code, 400)

    def test_sync_devices(self):
        # Test dry run sync of all devices
        data = {"all": True, "dry_run": True}
        result = self.client.post('/api/v1.0/device_sync', json=data)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
        self.assertEqual(type(result.json['job_id']), str)




if __name__ == '__main__':
    unittest.main()
