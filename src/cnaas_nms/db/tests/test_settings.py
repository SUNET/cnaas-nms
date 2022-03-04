import os
import yaml
import unittest
import pkg_resources

from cnaas_nms.db.settings import get_settings, verify_dir_structure, \
    DIR_STRUCTURE, VerifyPathException, \
    check_vlan_collisions, VlanConflictError, \
    get_groups_priorities_sorted, get_device_primary_groups, \
    check_group_priority_collisions
from cnaas_nms.db.device import DeviceType

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

    def test_groups_priorities_sorted(self):
        group_settings_dict = {
            "groups": [
                {
                    "group": {
                        "name": "DEFAULT",
                        "group_priority": 1
                    },
                },
                {
                    "group": {
                        "name": "HIGH",
                        "group_priority": 100
                    }
                },
                {
                    "group": {
                        "name": "NONE",
                        "group_priority": 0
                    }
                },
            ]
        }
        result = get_groups_priorities_sorted(settings=group_settings_dict)
        self.assertEqual(list(result.keys()),
                         ['HIGH', 'DEFAULT', 'NONE'],
                         "Unexpected ordering of groups sorted by priority")
        self.assertNotEqual(list(result.keys()),
                            ['NONE', 'DEFAULT', 'HIGH'],
                            "Unexpected ordering of groups sorted by priority")

    def test_get_device_primary_group(self):
        before = get_device_primary_groups()
        after = get_device_primary_groups(no_cache=True)
        self.assertEqual(before, after)

    def test_groups_priorities_collission(self):
        group_settings_dict = {
            "groups": [
                {
                    "group": {
                        "name": "DEFAULT",
                        "group_priority": 1
                    },
                },
                {
                    "group": {
                        "name": "HIGH",
                        "group_priority": 100
                    }
                },
                {
                    "group": {
                        "name": "DUPLICATE",
                        "group_priority": 100
                    }
                },
            ]
        }
        with self.assertRaises(ValueError,
                               msg="Groups with same priority should raise ValueError"):
            check_group_priority_collisions(group_settings_dict)
        # Remove duplicate entry
        del group_settings_dict['groups'][2]
        self.assertIsNone(check_group_priority_collisions(group_settings_dict))


if __name__ == '__main__':
    unittest.main()
