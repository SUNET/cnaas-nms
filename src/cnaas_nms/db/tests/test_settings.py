import os
import yaml
import unittest
import pkg_resources

from cnaas_nms.db.settings import get_settings, verify_dir_structure, \
    DIR_STRUCTURE, VerifyPathException
from cnaas_nms.db.device import DeviceType

class SettingsTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)
        self.required_setting_keys = ['ntp_servers', 'radius_servers']

    def test_get_settings_global(self):
        settings, settings_origin = get_settings()
        # Assert that all required settings are set
        self.assertTrue(all(k in settings for k in self.required_setting_keys))

    def test_get_settings_devicetype(self):
        settings, settings_origin = get_settings(device_type=DeviceType.DIST)
        # Assert that all required settings are set
        self.assertTrue(all(k in settings for k in self.required_setting_keys))

    def test_get_settings_device(self):
        settings, settings_origin = get_settings(
            hostname=self.testdata['testdevice'], device_type=DeviceType.DIST)
        # Assert that all required settings are set
        self.assertTrue(all(k in settings for k in self.required_setting_keys))

    def test_settings_pathverification(self):
        # Assert that directory structure is actually verified by making sure an
        # is raised when looking in the filesystem root
        self.assertRaises(VerifyPathException, verify_dir_structure, '', DIR_STRUCTURE)


if __name__ == '__main__':
    unittest.main()
