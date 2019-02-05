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
        # Exactly one result
        self.assertEqual(len(result.json), 1)
        # The one result should have the same ID we asked for
        self.assertEqual(result.json[0]['id'], device_id)

if __name__ == '__main__':
    unittest.main()
