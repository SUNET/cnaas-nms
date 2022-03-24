import os
import unittest

import pkg_resources
import yaml

from cnaas_nms.api import app
from cnaas_nms.api.tests.app_wrapper import TestAppWrapper


class SettingsTests(unittest.TestCase):
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

    def test_invalid_setting(self):
        settings_data = {"ntp_servers": [{"host": "10.0.0.500"}]}
        result = self.client.post("/api/v1.0/settings/model", json=settings_data)
        self.assertEqual(result.status_code, 400)

    def test_valid_setting(self):
        settings_data = {"ntp_servers": [{"host": "10.0.0.50"}]}
        result = self.client.post("/api/v1.0/settings/model", json=settings_data)
        self.assertEqual(result.status_code, 200)


if __name__ == "__main__":
    unittest.main()
