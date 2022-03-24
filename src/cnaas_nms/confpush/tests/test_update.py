import unittest
import pkg_resources
import yaml
import os

from cnaas_nms.confpush.update import update_linknets
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import DeviceType
from cnaas_nms.db.interface import InterfaceError


class UpdateTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)

    def test_update_linknet_eosaccess(self):
        with sqla_session() as session:
            neighbors_data = {
                "Ethernet2": [{"hostname": "eosdist1", "port": "Ethernet2"}],
                "Ethernet3": [{"hostname": "eosdist2", "port": "Ethernet2"}],
            }
            linknets = update_linknets(session, hostname="eosaccess",
                                       devtype=DeviceType.ACCESS, ztp_hostname="eosaccess",
                                       dry_run=True, neighbors_arg=neighbors_data)
            self.assertListEqual(
                linknets,
                [{'description': None, 'device_a_hostname': 'eosaccess', 'device_a_ip': None,
                  'device_a_port': 'Ethernet2', 'device_b_hostname': 'eosdist1',
                  'device_b_ip': None, 'device_b_port': 'Ethernet2', 'ipv4_network': None,
                  'redundant_link': True, 'site_id': None},
                 {'description': None, 'device_a_hostname': 'eosaccess', 'device_a_ip': None,
                  'device_a_port': 'Ethernet3', 'device_b_hostname': 'eosdist2',
                  'device_b_ip': None, 'device_b_port': 'Ethernet2', 'ipv4_network': None,
                  'redundant_link': True, 'site_id': None}],
                "Update linknets returned unexpected data for eosaccess links"
            )

    def test_update_linknet_wrong_porttype(self):
        with sqla_session() as session:
            neighbors_data = {
                "Ethernet2": [{"hostname": "eosdist1", "port": "Ethernet1"}],
                "Ethernet3": [{"hostname": "eosdist2", "port": "Ethernet1"}],
            }
            self.assertRaises(
                InterfaceError, update_linknets, session, hostname="eosaccess",
                devtype=DeviceType.ACCESS, ztp_hostname="eosaccess",
                dry_run=True, neighbors_arg=neighbors_data)


if __name__ == '__main__':
    unittest.main()
