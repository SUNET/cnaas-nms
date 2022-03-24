import os
import pprint
import unittest

import pkg_resources
import yaml

import cnaas_nms.confpush.get
import cnaas_nms.confpush.update
from cnaas_nms.db.device import DeviceType
from cnaas_nms.db.session import sqla_session


class GetTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, "data")
        with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)

    def test_get_inventory(self):
        result = cnaas_nms.confpush.get.get_inventory()
        pprint.pprint(result)  # noqa: T003
        # Inventory dict should contain these top level keys
        self.assertListEqual(["hosts", "groups", "defaults"], list(result.keys()))
        # Hosts key should include atleast 1 item
        self.assertLessEqual(1, len(result["hosts"].items()))

    def equipmenttest_update_links(self):
        with sqla_session() as session:
            new_links = cnaas_nms.confpush.update.update_linknets(
                session, self.testdata["init_access_new_hostname"], DeviceType.ACCESS
            )
        pprint.pprint(new_links)  # noqa: T003


if __name__ == "__main__":
    unittest.main()
