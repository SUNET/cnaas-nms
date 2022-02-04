import os
import unittest

import pkg_resources
import yaml

from cnaas_nms.db.device import DeviceType
from cnaas_nms.db.settings import (
    DIR_STRUCTURE,
    VerifyPathException,
    VlanConflictError,
    check_vlan_collisions,
    get_settings,
    verify_dir_structure,
)


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

    def test_vlan_collisions(self):
        mgmt_vlans = {100}
        # Check colliding mgmt vlan
        devices_dict = {
            'device1': {
                'vxlans': {
                    'vxlan1': {
                        'vni': 100100,
                        'vrf': 'vrf1',
                        'vlan_id': 100,
                        'vlan_name': 'vlanname1',
                        'ipv4_gw': '10.0.0.1/24'
                    }
                }
            }
        }
        self.assertRaises(VlanConflictError, check_vlan_collisions, devices_dict, mgmt_vlans)
        # Check colliding vxlan vni in same device
        devices_dict = {
            'device1': {
                'vxlans': {
                    'vxlan1': {
                        'vni': 100200,
                        'vrf': 'vrf1',
                        'vlan_id': 200,
                        'vlan_name': 'vlanname1',
                        'ipv4_gw': '10.0.0.1/24'
                    },
                }
            },
            'device2': {
                'vxlans': {
                    'vxlan2': {
                        'vni': 100200,
                        'vrf': 'vrf1',
                        'vlan_id': 201,
                        'vlan_name': 'vlanname1',
                        'ipv4_gw': '10.0.1.1/24'
                    }
                }
            }
        }
        self.assertRaises(VlanConflictError, check_vlan_collisions, devices_dict, mgmt_vlans)
        # Check colliding vlan_id in same device
        devices_dict = {
            'device1': {
                'vxlans': {
                    'vxlan1': {
                        'vni': 100200,
                        'vrf': 'vrf1',
                        'vlan_id': 200,
                        'vlan_name': 'vlanname1',
                        'ipv4_gw': '10.0.0.1/24'
                    },
                    'vxlan2': {
                        'vni': 100201,
                        'vrf': 'vrf1',
                        'vlan_id': 200,
                        'vlan_name': 'vlanname2',
                        'ipv4_gw': '10.0.1.1/24'
                    }
                }
            }
        }
        self.assertRaises(VlanConflictError, check_vlan_collisions, devices_dict, mgmt_vlans)
        # Check colliding vlan name in same device
        devices_dict = {
            'device1': {
                'vxlans': {
                    'vxlan1': {
                        'vni': 100200,
                        'vrf': 'vrf1',
                        'vlan_id': 200,
                        'vlan_name': 'vlanname1',
                        'ipv4_gw': '10.0.0.1/24'
                    },
                    'vxlan2': {
                        'vni': 100201,
                        'vrf': 'vrf1',
                        'vlan_id': 201,
                        'vlan_name': 'vlanname1',
                        'ipv4_gw': '10.0.1.1/24'
                    }
                }
            }
        }
        self.assertRaises(VlanConflictError, check_vlan_collisions, devices_dict, mgmt_vlans)
        # Check valid config
        devices_dict = {
            'device1': {
                'vxlans': {
                    'vxlan1': {
                        'vni': 100200,
                        'vrf': 'vrf1',
                        'vlan_id': 200,
                        'vlan_name': 'vlanname1',
                        'ipv4_gw': '10.0.0.1/24'
                    },
                }
            },
            'device2': {
                'vxlans': {
                    'vxlan2': {
                        'vni': 100201,
                        'vrf': 'vrf1',
                        'vlan_id': 201,
                        'vlan_name': 'vlanname1',
                        'ipv4_gw': '10.0.1.1/24'
                    }
                }
            }
        }
        self.assertIsNone(check_vlan_collisions(devices_dict, mgmt_vlans))


if __name__ == '__main__':
    unittest.main()
