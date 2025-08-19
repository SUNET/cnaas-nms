#!/usr/bin/env python3

import unittest

from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.settings_fields import f_group


class GroupsTest(unittest.TestCase):
    def setUp(self):
        self.eosaccess_device = Device(hostname="access1", platform="eos", device_type=DeviceType.ACCESS)
        self.iosaccess_device = Device(hostname="access2", platform="ios", device_type=DeviceType.ACCESS)
        self.eosdist_device = Device(hostname="dist1", platform="eos", device_type=DeviceType.DIST)
        self.iosdist_device = Device(hostname="dist2", platform="ios", device_type=DeviceType.DIST)

    def test_groups_deprecated(self):
        # Test that the old group format is converted to the new format
        old_group = f_group(**{"group": {"name": "GROUP", "regex": ".*"}}).model_dump_json()
        new_group = f_group(name="GROUP", device_filter={"hostname": ".*"}).model_dump_json()
        self.assertEqual(old_group, new_group)

    def test_groups(self):
        # error when device_filter and devices are both set
        with self.assertRaises(ValueError):
            f_group(name="INVALID_GROUP", device_filter={"device_type": "ACCESS"}, devices=["access1"])

    def test_groups_empty_name(self):
        with self.assertRaises(ValueError):
            f_group(name=None)

    def test_groups_empty_device_filter(self):
        group = f_group(name="EMPTY_DEVICE_FILTER", device_filter={})
        # Match on empty device filter
        self.assertFalse(group.matches(self.eosaccess_device))
        self.assertFalse(group.matches(self.iosaccess_device))
        self.assertFalse(group.matches(self.eosdist_device))
        self.assertFalse(group.matches(self.iosdist_device))

    def test_groups_empty_devices(self):
        group = f_group(name="EMPTY_DEVICES", devices=[])
        # Match on empty device filter
        self.assertFalse(group.matches(self.eosaccess_device))
        self.assertFalse(group.matches(self.iosaccess_device))
        self.assertFalse(group.matches(self.eosdist_device))
        self.assertFalse(group.matches(self.iosdist_device))

    def test_groups_device_filter_hostname(self):
        group = f_group(name="ACCESS_REGEX_HOSTNAME", device_filter={"hostname": "^.*access.*$"})
        # Match on hostname
        self.assertTrue(group.matches(self.eosaccess_device))
        self.assertFalse(group.matches(self.eosdist_device))

        self.assertTrue(group.matches(self.iosaccess_device))
        self.assertFalse(group.matches(self.iosdist_device))

    def test_groups_device_filter_device_type(self):
        group1 = f_group(name="ACCESS_ENUM_TYPE", device_filter={"device_type": "ACCESS"})
        group2 = f_group(name="ACCESS_DIST_REGEX_TYPE", device_filter={"device_type": "ACCESS|DIST|CORE"})
        # Match on device type enum
        self.assertTrue(group1.matches(self.eosaccess_device))
        self.assertFalse(group1.matches(self.eosdist_device))

        self.assertTrue(group1.matches(self.iosaccess_device))
        self.assertFalse(group1.matches(self.iosdist_device))

        # Match on device type regex
        self.assertTrue(group2.matches(self.eosaccess_device))
        self.assertTrue(group2.matches(self.eosdist_device))

        self.assertTrue(group2.matches(self.iosaccess_device))
        self.assertTrue(group2.matches(self.iosdist_device))

    def test_groups_device_filter_platform(self):
        group1 = f_group(name="EOS_ACCESS", device_filter={"device_type": "ACCESS", "platform": "eos"})
        group2 = f_group(name="IOS_DIST", device_filter={"device_type": "DIST", "platform": "ios"})
        # Match on platform eos + access
        self.assertTrue(group1.matches(self.eosaccess_device))
        self.assertFalse(group1.matches(self.iosaccess_device))
        self.assertFalse(group1.matches(self.eosdist_device))
        self.assertFalse(group1.matches(self.iosdist_device))
        # Match on platform ios + dist
        self.assertTrue(group2.matches(self.iosdist_device))
        self.assertFalse(group2.matches(self.eosdist_device))
        self.assertFalse(group2.matches(self.eosaccess_device))
        self.assertFalse(group2.matches(self.iosaccess_device))

    def test_groups_device_filter_devices(self):
        group = f_group(name="ALL_DEVICES", devices=["access1", "access2", "dist1", "dist2"])
        # Match on device list
        self.assertTrue(group.matches(self.eosaccess_device))
        self.assertTrue(group.matches(self.iosaccess_device))
        self.assertTrue(group.matches(self.eosdist_device))
        self.assertTrue(group.matches(self.iosdist_device))

        # Check that a device not in the group does not match
        self.assertFalse(group.matches(Device(hostname="unknown", platform="unknown", device_type=DeviceType.ACCESS)))
