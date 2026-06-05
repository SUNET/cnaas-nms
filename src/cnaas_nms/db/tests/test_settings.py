import os
import unittest
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

import cnaas_nms.db.settings as db_settings_module
from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.session import redis_session, sqla_session
from cnaas_nms.db.settings import (
    DIR_STRUCTURE,
    AccessListGenerationError,
    NMSRedisLRU,
    SettingsSyntaxError,
    VerifyPathException,
    VlanConflictError,
    check_bgp_neighbor_routemaps,
    check_system_access_lists,
    check_vlan_collisions,
    f_root,
    get_device_primary_groups,
    get_generated_access_lists,
    get_group_settings,
    get_groups_priorities_sorted,
    get_settings,
    rebuild_settings_cache,
    verify_dir_structure,
)
from cnaas_nms.db.settings_fields import f_access_list, f_group, f_groups


class SettingsTests(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def requirements(self, postgresql, redis):
        """Ensures database fixtures are loaded for all tests."""
        pass

    def setUp(self):
        data_dir = Path(__file__).parent / "data"
        with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)
        self.required_setting_keys = ["ntp_servers", "radius_servers"]
        self.cleandb()

    def tearDown(self):
        self.cleandb()

    def cleandb(self):
        with redis_session() as redis:  # type: ignore
            cache = NMSRedisLRU(redis)
            cache.clear_all_cache()
        with sqla_session() as session:  # type: ignore
            for hostname in ["testgroup_dev1"]:
                device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
                if device:
                    session.delete(device)
                    session.commit()
                    rebuild_settings_cache()

    @pytest.mark.integration
    @pytest.mark.usefixtures("settings_directory")
    def test_get_settings_global(self):
        settings, _ = get_settings()
        # Assert that all required settings are set
        self.assertTrue(all(k in settings for k in self.required_setting_keys))

    @pytest.mark.integration
    @pytest.mark.usefixtures("settings_directory")
    def test_get_settings_devicetype(self):
        settings, _ = get_settings(device_type=DeviceType.DIST)
        # Assert that all required settings are set
        self.assertTrue(all(k in settings for k in self.required_setting_keys))

    @pytest.mark.integration
    @pytest.mark.usefixtures("settings_directory")
    def test_get_settings_device(self):
        settings, _ = get_settings(device=Device(hostname=self.testdata["testdevice"]), device_type=DeviceType.DIST)
        # Assert that all required settings are set
        self.assertTrue(all(k in settings for k in self.required_setting_keys))

    @pytest.mark.integration
    @pytest.mark.usefixtures("settings_directory")
    def test_get_settings_merge_keys(self):
        testgroup_dev1 = Device(hostname="testgroup_dev1", state="MANAGED", device_type=DeviceType.DIST)
        with sqla_session() as session:
            session.add(testgroup_dev1)
            session.flush()
            session.expunge(testgroup_dev1)

        rebuild_settings_cache()

        settings, _ = get_settings(device=testgroup_dev1)

        self.assertTrue("DEFAULT" in settings["prefix_sets"])
        self.assertTrue("infra-cpe-loopbacks" in settings["prefix_sets"])
        self.assertTrue("allow_default" in settings["routing_policies"])
        self.assertTrue("allow_infra_loopback" in settings["routing_policies"])

    @pytest.mark.integration
    @pytest.mark.usefixtures("settings_directory")
    def test_get_settings_redis_hit(self):
        """
        Run get_settings twice with the same device should execute get_settings only once
        """
        # Clear redis_cache
        with redis_session() as redis:  # type: ignore
            cache = NMSRedisLRU(redis)
            cache.clear_all_cache()

        # Counter to track actual executions
        call_count = {"count": 0}

        # Save the original undecorated logic
        original_func = db_settings_module.get_settings

        # Define a spy wrapper
        def spy_get_settings(*args, **kwargs):
            call_count["count"] += 1
            return original_func(*args, **kwargs)

        # Reapply NMSRedisLRU decorator to the spy
        db_settings_module.get_settings = db_settings_module.redis_lru_cache(spy_get_settings)

        # First call, executes get_settings
        settings1, _ = db_settings_module.get_settings(
            device=Device(hostname=self.testdata["testdevice"]), device_type=DeviceType.DIST
        )

        # Second call, should hit the cache
        settings2, _ = db_settings_module.get_settings(
            device=Device(hostname=self.testdata["testdevice"]), device_type=DeviceType.DIST
        )

        # Assert get_settings runs once
        assert call_count["count"] == 1

        # Assert results are identical
        assert settings1 == settings2

    def test_settings_pathverification(self):
        # Assert that directory structure is actually verified by making sure an
        # is raised when looking in the filesystem root
        self.assertRaises(VerifyPathException, verify_dir_structure, "", DIR_STRUCTURE)

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
        result = get_groups_priorities_sorted(settings=f_groups(**group_settings_dict))
        # Groups with priority 0 is not evaluated in selecting primary group
        self.assertEqual(list(result.keys()), ["HIGH", "DEFAULT"], "Unexpected ordering of groups sorted by priority")
        self.assertNotEqual(
            list(result.keys()), ["DEFAULT", "HIGH"], "Unexpected ordering of groups sorted by priority"
        )

    @pytest.mark.integration
    @pytest.mark.usefixtures("settings_directory")
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

    @pytest.mark.integration
    @pytest.mark.usefixtures("settings_directory")
    def test_group_settings(self):
        settings, _ = get_group_settings()
        for group in settings.groups:
            self.assertEqual(type(group), f_group)
            assert callable(group.matches)

    @pytest.mark.integration
    @pytest.mark.usefixtures("settings_directory")
    def test_acl(self):
        """Generate global acls from integration-test repo"""
        for platform in ["ios", "eos", "junos"]:
            device = Device(hostname=self.testdata["testdevice"], platform=platform)
            get_generated_access_lists(device)

    def test_acl_option(self):
        """Test validate and generate access list option"""
        settings = {
            "access_lists": {
                "TEST_ACL_ESTABLISHED": {
                    "terms": [
                        {
                            "name": "permit-established",
                            "protocol": ["tcp", "udp"],
                            "option": "established",
                            "action": "accept",
                        }
                    ]
                },
                "TEST_ACL_TCP_ESTABLISHED": {
                    "terms": [
                        {
                            "name": "permit-tcp-established",
                            "protocol": ["tcp"],
                            "option": "tcp-established",
                            "action": "accept",
                        }
                    ]
                },
            },
            "system_access_lists": ["TEST_ACL_ESTABLISHED", "TEST_ACL_TCP_ESTABLISHED"],
        }
        # Validate and generate
        f_root(**settings)
        acls = get_generated_access_lists(platform="eos", settings=settings)
        self.assertEqual(len(acls.keys()), 2)

    def test_acl_invalid_definition(self):
        """Test invalid network definitions"""
        settings = {
            "network_definitions": {
                "ONEONEONEONE": [{"address": "1.1.1.1"}, {"address": "2606:4700:4700::1111"}],  # noqa: S1313
                "ONEZEROZEROONE": [{"address": "1.0.0.1"}, {"address": "2606:4700:4700::1001"}],  # noqa: S1313
                "BOTH": [{"name": "ONEONE"}, {"name": "ONEZEROZEROONE"}],
            },
            "access_lists": {
                "TEST_ACL": {"terms": [{"name": "permit-all", "source-address": "BOTH", "action": "accept"}]}
            },
            "system_access_lists": ["TEST_ACL"],
        }
        with self.assertRaises(AccessListGenerationError):
            get_generated_access_lists(platform="eos", settings=settings)

    def test_acl_no_terms(self):
        """Test acl no terms"""
        settings = {
            "access_lists": {"TEST_ACL": {"terms": []}},
        }
        with self.assertRaises(ValidationError):
            f_root(**settings)

    def test_acl_non_unique_terms(self):
        """Test acl non unique terms"""
        settings = {
            "access_lists": {"TEST_ACL": {"terms": [{"name": "same"}, {"name": "same"}]}},
        }
        with self.assertRaises(ValidationError):
            f_root(**settings)

    def test_acl_include_not_found(self):
        """Test include acl not found"""
        settings = {
            "access_lists": {"TEST_ACL": {"terms": [{"include": "NOT-FOUND-ACL"}]}},
        }
        with self.assertRaises(ValidationError):
            f_root(**settings)

    def test_acl_include(self):
        """Test include acl"""
        settings = {
            "access_lists": {
                "INCLUDE-ACL": {"terms": [{"name": "some-acl", "action": "accept"}]},
                "TEST_ACL": {"terms": [{"include": "INCLUDE-ACL"}]},
            },
            "system_access_lists": ["TEST_ACL"],
        }
        f_root(**settings)
        acls = get_generated_access_lists(platform="eos", settings=settings)
        self.assertIn("TEST_ACL", acls.keys())
        self.assertEqual(len(acls), 1)

    def test_acl_nested_include(self):
        """Test include acl"""
        settings = {
            "access_lists": {
                "INCLUDE-ACL1": {"terms": [{"include": "INCLUDE-ACL2"}]},
                "INCLUDE-ACL2": {"terms": [{"include": "INCLUDE-ACL3"}]},
                "INCLUDE-ACL3": {"terms": [{"include": "INCLUDE-ACL4"}]},
                "INCLUDE-ACL4": {"terms": [{"name": "some-acl", "action": "accept"}]},
                "TEST_ACL": {"terms": [{"include": "INCLUDE-ACL1"}]},
            },
            "system_access_lists": ["TEST_ACL"],
        }
        f_root(**settings)
        acls = get_generated_access_lists(platform="eos", settings=settings)
        self.assertIn("TEST_ACL", acls.keys())
        self.assertEqual(len(acls), 1)

    def test_acl_include_non_unique(self):
        """Test include acl where the included terms are not unique together with the parent term names"""
        settings = {
            "access_lists": {
                "INCLUDE-ACL": {"terms": [{"name": "not-unique"}]},
                "TEST_ACL": {"terms": [{"include": "INCLUDE-ACL"}, {"name": "not-unique"}]},
            },
        }
        with self.assertRaises(ValidationError):
            f_root(**settings)

    @pytest.mark.integration
    @pytest.mark.usefixtures("settings_directory")
    def test_acl_redis_hit(self):
        """
        Run get_generated_access_lists twice with the same device should execute get_settings only once
        """
        # Clear redis_cache
        with redis_session() as redis:  # type: ignore
            cache = NMSRedisLRU(redis)
            cache.clear_all_cache()

        # Counter to track actual executions
        call_count = {"count": 0}

        # Save the original undecorated logic
        original_func = db_settings_module._generate_acl

        # Define a spy wrapper
        def spy_generate_acl(*args, **kwargs):
            call_count["count"] += 1
            return original_func(*args, **kwargs)

        # Reapply NMSRedisLRU decorator to the spy
        db_settings_module._generate_acl = db_settings_module.redis_lru_cache(spy_generate_acl)

        # First call, executes get_settings
        # Both devices should get global settings
        acls1 = db_settings_module.get_generated_access_lists(Device(hostname="acl-testdevice-a1", platform="eos"))

        acls2 = db_settings_module.get_generated_access_lists(Device(hostname="acl-testdevice-a1", platform="eos"))

        # Assert _generate_acl runs once
        assert call_count["count"] == 1

        # Assert results are identical
        assert acls1 == acls2

    def test_acl_system_acl(self):
        system_acls = ["ACL-TEST"]
        acls = {"ACL-TEST": {"terms": [{"name": "permit-any", "action": "accept"}]}}
        # Works because the system_access_list is defined in access_lists
        check_system_access_lists({"system_access_lists": system_acls, "access_lists": acls})

        with self.assertRaises(SettingsSyntaxError):
            check_system_access_lists({"system_access_lists": system_acls, "access_lists": {}})

    def test_acl_auto_from_vxlans(self):
        """vxlan that is allocated to a DeviceType.DIST will be auto included to be generated"""
        settings = {
            "vrfs": [{"name": "SOME_VRF", "vrf_id": 101}],
            "vxlans": {
                "SOME_VXLAN": {
                    "vni": 100101,
                    "vrf": "SOME_VRF",
                    "vlan_id": 101,
                    "vlan_name": "SOME_VXLAN",
                    "ipv4_gw": "192.168.0.1/24",  # noqa: S1313
                    "acl_ipv4_in": "SOME_VXLAN_IN",
                    "devices": ["testdevice-d1"],
                }
            },
            "access_lists": {"SOME_VXLAN_IN": {"terms": [{"name": "permit-any", "action": "accept"}]}},
        }

        # Validate settings
        f_root(**settings)
        # For a dist-switch it will automatically get and generate vxlan access-lists if found in access_lists.
        dist_acls = get_generated_access_lists(
            Device(hostname="testdevice-d1", platform="eos", device_type=DeviceType.DIST), settings=settings
        )

        self.assertIn("SOME_VXLAN_IN", dist_acls.keys())
        self.assertEqual(len(dist_acls), 1)

        # For access it will not be generated
        access_acls = get_generated_access_lists(
            Device(hostname="testdevice-a1", platform="eos", device_type=DeviceType.ACCESS), settings=settings
        )

        self.assertNotIn("SOME_VXLAN_IN", access_acls.keys())
        self.assertEqual(len(access_acls), 0)

    def test_acl_auto_from_interfaces(self):
        """interfaces that is allocated to a device will be auto included to be generated"""
        settings = {
            "vrfs": [{"name": "SOME_VRF", "vrf_id": 101}],
            "interfaces": [
                {
                    "name": "Ethernet1",
                    "ifclass": "custom",
                    "vrf": "SOME_VRF",
                    "ipv4_address": "192.168.0.1/24",  # noqa: S1313
                    "acl_ipv4_in": "SOME_INTF_IN",
                }
            ],
            "access_lists": {"SOME_INTF_IN": {"terms": [{"name": "permit-any", "action": "accept"}]}},
        }

        # Validate settings
        f_root(**settings)
        # For all device-types if access lists are set on interfaces it will automatically generate them
        for devtype in [DeviceType.ACCESS, DeviceType.CORE, DeviceType.DIST, DeviceType.FIREWALL]:
            acls = get_generated_access_lists(
                Device(hostname="testdevice-x1", platform="eos", device_type=devtype), settings=settings
            )

            self.assertIn("SOME_INTF_IN", acls.keys())
            self.assertEqual(len(acls), 1)

    def test_acl_juniper_srx(self):
        settings = {
            "vrfs": [{"name": "SOME_VRF", "vrf_id": 101}],
            "interfaces": [
                {
                    "name": "Ethernet1",
                    "ifclass": "custom",
                    "vrf": "SOME_VRF",
                    "ipv4_address": "192.168.0.1/24",  # noqa: S1313
                    "acl_ipv4_in": "ALL_TO_ALL",
                }
            ],
            "access_lists": {
                "ALL_TO_ALL": {
                    "header_map": {"srx": "from-zone all to-zone all {INET_FAMILY}"},
                    "terms": [{"name": "permit-any", "action": "accept"}],
                }
            },
        }

        # Validate settings
        f_root(**settings)

        firewall_device = Device(
            hostname="test-fw1", platform="junos", device_type=DeviceType.FIREWALL, model="SRX380-POE-AC"
        )
        acls = get_generated_access_lists(firewall_device, settings=settings)
        self.assertIn("ALL_TO_ALL", acls.keys())
        self.assertEqual(len(acls), 1)

    def test_acl_juniper_srx_error(self):
        settings = {
            "vrfs": [{"name": "SOME_VRF", "vrf_id": 101}],
            "interfaces": [
                {
                    "name": "Ethernet1",
                    "ifclass": "custom",
                    "vrf": "SOME_VRF",
                    "ipv4_address": "192.168.0.1/24",  # noqa: S1313
                    "acl_ipv4_in": "ALL_TO_ALL",
                }
            ],
            "access_lists": {"ALL_TO_ALL": {"terms": [{"name": "permit-any", "action": "accept"}]}},
        }

        # Validate settings
        f_root(**settings)

        firewall_device = Device(
            hostname="test-fw1", platform="junos", device_type=DeviceType.FIREWALL, model="SRX380-POE-AC"
        )

        # Cannot render SRX acl without a custom header map
        with self.assertRaises(AccessListGenerationError):
            get_generated_access_lists(firewall_device, settings=settings)

    def test_acl_f_access_list_header_map(self):
        """Verify f_access_list header_map, can be in napalm or aerleon platform syntax."""
        data = {
            "header_map": {"ios": "", "eos": "", "srx": "", "nxos": "", "cisconx": ""},
            "terms": [{"name": "permit-any", "action": "accept"}],
        }
        f_access_list(**data)

    def test_acl_f_access_list_header_map_error(self):
        """Verify f_access_list header_map error"""
        # Invalid header_map key
        data = {"header_map": {"abc": "abc"}, "terms": [{"name": "permit-any", "action": "accept"}]}
        with self.assertRaises(ValidationError):
            f_access_list(**data)


if __name__ == "__main__":
    unittest.main()
