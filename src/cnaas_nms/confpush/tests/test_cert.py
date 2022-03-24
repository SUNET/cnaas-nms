import unittest
import pkg_resources
import yaml
import os

from nornir_utils.plugins.functions import print_result

from cnaas_nms.confpush.nornir_helper import cnaas_init
from cnaas_nms.confpush.cert import arista_copy_cert


class CertTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, "data")
        with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)

    def copy_cert(self):
        nr = cnaas_init()
        nr_filtered = nr.filter(name=self.testdata["copycert_hostname"])

        nrresult = nr_filtered.run(task=arista_copy_cert)
        if nrresult.failed:
            print_result(nrresult)
        self.assertFalse(nrresult.failed, "Task arista_copy_cert returned failed status")


if __name__ == "__main__":
    unittest.main()
