import cnaas_nms.confpush.get

import pprint

import unittest

class GetTests(unittest.TestCase):
    def test_get_inventory(self):
        result = cnaas_nms.confpush.get.get_inventory()
        pprint.pprint(result)
        # Inventory dict should contain these top level keys
        self.assertListEqual(
            ['hosts', 'groups', 'defaults'],
            list(result.keys()))
        # Hosts key should include atleast 1 item
        self.assertLessEqual(
            1,
            len(result['hosts'].items()))


if __name__ == '__main__':
    unittest.main()
