import os
import yaml
import unittest
import pkg_resources

from cnaas_nms.db.settings import get_settings, verify_dir_structure, \
    DIR_STRUCTURE, VerifyPathException

class SettingsTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)

    def test_get_settings(self):
        settings, settings_origin = get_settings()
        required_setting_keys = ['ntp_servers', 'radius_servers']
        # Assert that all required settings are set
        self.assertTrue(all(k in settings for k in required_setting_keys))
        # Assert that directory structure is actually verified by making sure an
        # is raised when looking in the filesystem root
        self.assertRaises(VerifyPathException, verify_dir_structure, '', DIR_STRUCTURE)


if __name__ == '__main__':
    unittest.main()
