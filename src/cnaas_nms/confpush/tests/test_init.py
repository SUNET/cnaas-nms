import cnaas_nms.confpush.init_device

import pprint
import unittest
import pkg_resources
import yaml
import os

class InitTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.load(f_testdata)

    def test_init_access_device(self):
        result = cnaas_nms.confpush.init_device.init_access_device('mac-080027F60C55')

if __name__ == '__main__':
    unittest.main()
