import unittest

from cnaas_nms.db.device import DeviceType
from cnaas_nms.db.git import template_syncstatus


class GitTests(unittest.TestCase):
    def test_check_unsync(self):
        devtypes = template_syncstatus({'eos/managed-full.j2'})
        for devtype in devtypes:
            self.assertEqual(type(devtype[0]), DeviceType)
            self.assertEqual(type(devtype[1]), str)
        self.assertTrue((DeviceType.ACCESS, 'eos') in devtypes)


if __name__ == '__main__':
    unittest.main()
