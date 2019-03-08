import pprint

import unittest

import cnaas_nms.api

class GetTests(unittest.TestCase):
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

if __name__ == '__main__':
    unittest.main()
