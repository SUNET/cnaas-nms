import os
import unittest

import pkg_resources
import pytest
import yaml
from pydantic import ValidationError

from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.settings import (
    DIR_STRUCTURE,
    VerifyPathException,
    VlanConflictError,
    check_bgp_neighbor_routemaps,
    check_vlan_collisions,
    get_device_primary_groups,
    get_groups_priorities_sorted,
    get_settings,
    verify_dir_structure,
)
from cnaas_nms.db.settings_fields import f_groups


class SettingsTests(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def requirements(self, postgresql, redis, settings_directory):
        """Ensures the required pytest fixtures are loaded implicitly for all these tests"""
        pass

    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, "data")
        with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)
        self.required_setting_keys = ["ntp_servers", "radius_servers"]

    @pytest.mark.integration
    def test_get_settings_global(self):
        settings, settings_origin = get_settings()
        # Assert that all required settings are set
        self.assertTrue(all(k in settings for k in self.required_setting_keys))

    @pytest.mark.integration
    def test_get_settings_devicetype(self):
        settings, settings_origin = get_settings(device_type=DeviceType.DIST)
        # Assert that all required settings are set
        self.assertTrue(all(k in settings for k in self.required_setting_keys))

    @pytest.mark.integration
    def test_get_settings_device(self):
        settings, settings_origin = get_settings(device=Device(**self.testdata["testdevice"]), device_type=DeviceType.DIST)
        # Assert that all required settings are set
        self.assertTrue(all(k in settings for k in self.required_setting_keys))

    def test_settings_pathverification(self):
        # Assert that directory structure is actually verified by making sure an
        # is raised when looking in the filesystem root
        self.assertRaises(VerifyPathException, verify_dir_structure, "", DIR_STRUCTURE)

    @pytest.mark.integration
    def test_vlan_collisions(self):
        mgmt_vlans = {100}
        # Check colliding mgmt vlan
        devices_dict = {
            "device1": {
                "vxlans": {
                    "vxlan1": {
                        "vni": 100100,
                        "vrf": "vrf1",
                        "vlan_id": 100,
                        "vlan_name": "vlanname1",
                        "ipv4_gw": "10.0.0.1/24",
                    }
                }
            }
        }
        self.assertRaises(VlanConflictError, check_vlan_collisions, devices_dict, mgmt_vlans)
        # Check colliding vxlan vni in same device
        devices_dict = {
            "device1": {
                "vxlans": {
                    "vxlan1": {
                        "vni": 100200,
                        "vrf": "vrf1",
                        "vlan_id": 200,
                        "vlan_name": "vlanname1",
                        "ipv4_gw": "10.0.0.1/24",
                    },
                }
            },
            "device2": {
                "vxlans": {
                    "vxlan2": {
                        "vni": 100200,
                        "vrf": "vrf1",
                        "vlan_id": 201,
                        "vlan_name": "vlanname1",
                        "ipv4_gw": "10.0.1.1/24",
                    }
                }
            },
        }
        self.assertRaises(VlanConflictError, check_vlan_collisions, devices_dict, mgmt_vlans)
        # Check colliding vlan_id in same device
        devices_dict = {
            "device1": {
                "vxlans": {
                    "vxlan1": {
                        "vni": 100200,
                        "vrf": "vrf1",
                        "vlan_id": 200,
                        "vlan_name": "vlanname1",
                        "ipv4_gw": "10.0.0.1/24",
                    },
                    "vxlan2": {
                        "vni": 100201,
                        "vrf": "vrf1",
                        "vlan_id": 200,
                        "vlan_name": "vlanname2",
                        "ipv4_gw": "10.0.1.1/24",
                    },
                }
            }
        }
        self.assertRaises(VlanConflictError, check_vlan_collisions, devices_dict, mgmt_vlans)
        # Check colliding vlan name in same device
        devices_dict = {
            "eosaccess": {
                "vxlans": {
                    "vxlan1": {
                        "vni": 100200,
                        "vrf": "vrf1",
                        "vlan_id": 200,
                        "vlan_name": "vlanname1",
                        "ipv4_gw": "10.0.0.1/24",
                    },
                    "vxlan2": {
                        "vni": 100201,
                        "vrf": "vrf1",
                        "vlan_id": 201,
                        "vlan_name": "vlanname1",
                        "ipv4_gw": "10.0.1.1/24",
                    },
                }
            }
        }
        self.assertRaises(VlanConflictError, check_vlan_collisions, devices_dict, mgmt_vlans)
        # Check valid config
        devices_dict = {
            "device1": {
                "vxlans": {
                    "vxlan1": {
                        "vni": 100200,
                        "vrf": "vrf1",
                        "vlan_id": 200,
                        "vlan_name": "vlanname1",
                        "ipv4_gw": "10.0.0.1/24",
                    },
                }
            },
            "device2": {
                "vxlans": {
                    "vxlan2": {
                        "vni": 100201,
                        "vrf": "vrf1",
                        "vlan_id": 201,
                        "vlan_name": "vlanname1",
                        "ipv4_gw": "10.0.1.1/24",
                    }
                }
            },
        }
        self.assertIsNone(check_vlan_collisions(devices_dict, mgmt_vlans))

    def test_routing_policy(self):
        test_device_name = "policytest"
        test_vrfs = [
            {
                "name": "testvrf",
                "neighbor_v4": [{"route_map_in": "routemap1", "route_map_out": "routemap1"}],
                "neighbor_v6": [{"route_map_in": "routemap2", "route_map_out": "routemap2"}],
            }
        ]
        with self.assertRaises(ValueError, msg="Undefined route map routemap1 should raise error"):
            check_bgp_neighbor_routemaps(test_device_name, test_vrfs, set())
        check_bgp_neighbor_routemaps(test_device_name, test_vrfs, {"routemap1", "routemap2"})
        with self.assertRaises(KeyError):
            check_bgp_neighbor_routemaps(test_device_name, [{"name": "emptyvrf"}], set())

    def test_groups_priorities_sorted(self):
        group_settings_dict = {
            "groups": [
                {"name": "DEFAULT", "group_priority": 1},
                {"name": "HIGH", "group_priority": 100},
                {"name": "NONE", "group_priority": 0},
            ]
        }
        result = get_groups_priorities_sorted(settings=group_settings_dict)
        # Groups with priority 0 is not evaluated in selecting primary group
        self.assertEqual(list(result.keys()), ["HIGH", "DEFAULT"], "Unexpected ordering of groups sorted by priority")
        self.assertNotEqual(
            list(result.keys()), ["DEFAULT", "HIGH"], "Unexpected ordering of groups sorted by priority"
        )

    @pytest.mark.integration
    def test_get_device_primary_group(self):
        before = get_device_primary_groups()
        after = get_device_primary_groups(no_cache=True)
        self.assertEqual(before, after)

    def test_groups_priorities_collission(self):
        group_settings_dict = {
            "groups": [
                {"name": "DEFAULT", "group_priority": 1},
                {"name": "HIGH", "group_priority": 100},
                {"name": "DUPLICATE", "group_priority": 100},
            ]
        }

        with self.assertRaises(ValueError, msg="Groups with same priority should raise ValueError"):
            f_groups(**group_settings_dict)
        # Remove duplicate entry
        del group_settings_dict["groups"][2]
        f_groups(**group_settings_dict)

    def test_groups_names_collission(self):
        group_settings_dict = {
            "groups": [
                {"name": "DEFAULT", "group_priority": 1},
                {"name": "OTHER_GROUP"},
                {"name": "DEFAULT"},
            ]
        }

        with self.assertRaises(ValueError, msg="Groups with same name should raise ValueError"):
            f_groups(**group_settings_dict)
        # Remove duplicate entry
        del group_settings_dict["groups"][2]
        f_groups(**group_settings_dict)

    def test_groups_device_filter(self):
        group_settings_dict = {
            "groups": [
                {"name": "DEFAULT", "group_priority": 1},
                {"name": "GROUP1", "device_filter": {"hostname": "eosdist1$"}},
                {"name": "ERROR_GROUP", "device_filter": {"hostname": "eosdist1$("}},
            ]
        }

        with self.assertRaises(ValueError, msg="Groups with bad regex should raise ValueError"):
            f_groups(**group_settings_dict)
        # Remove bad entry
        del group_settings_dict["groups"][2]
        f_groups(**group_settings_dict)

    def test_groups_templates_branches(self):
        group_settings_dict = {
            "groups": [
                {"name": "DEFAULT", "group_priority": 1},
                {
                    "name": "TEMPLATE1",
                    "device_filter": {"hostname": "eosdist1$"},
                    "group_priority": 100,
                    "templates_branch": "test1",
                },
                {"name": "NOT_PRIMARY_GROUP", "templates_branch": "test2"},
            ]
        }
        with self.assertRaises(
            ValidationError,
            msg="Group with template_branch set but no group_priority value should raise ValidationError",
        ):
            f_groups(**group_settings_dict).model_dump()

        # Remove bad entry
        del group_settings_dict["groups"][2]
        f_groups(**group_settings_dict).model_dump()


if __name__ == "__main__":
    unittest.main()
