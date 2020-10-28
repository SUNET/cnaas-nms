import cnaas_nms.confpush.get

import pprint
import unittest
import pkg_resources
import yaml
import os

from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import DeviceType


class GetTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)

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

    def test_get_facts(self):
        result = cnaas_nms.confpush.get.get_facts(group='S_DHCP_BOOT')
        pprint.pprint(result)

    def test_update_inventory(self):
        diff = cnaas_nms.confpush.get.update_inventory(self.testdata['update_hostname'])
        pprint.pprint(diff)

    def test_update_links(self):
        with sqla_session() as session:
            new_links = cnaas_nms.confpush.get.update_linknets(
                session, self.testdata['update_hostname'], DeviceType.ACCESS)
        pprint.pprint(new_links)


if __name__ == '__main__':
    unittest.main()
