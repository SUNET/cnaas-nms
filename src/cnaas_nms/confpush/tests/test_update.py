import unittest
import pkg_resources
import yaml
import os

from cnaas_nms.confpush.update import update_linknets
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import DeviceType


class UpdateTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)

    def test_update_linknet(self):
        with sqla_session() as session:
            neighbors_data = {
                "Ethernet2": [{"hostname": "eosdist1", "port": "Ethernet2"}],
                "Ethernet3": [{"hostname": "eosdist2", "port": "Ethernet2"}],
            }
            linknets = update_linknets(session, hostname="eosaccess",
                                       devtype=DeviceType.ACCESS, ztp_hostname="eosaccess",
                                       dry_run=True, neighbors_arg=neighbors_data)
            breakpoint()
            print(linknets)


if __name__ == '__main__':
    unittest.main()
