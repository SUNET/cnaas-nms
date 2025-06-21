#!/usr/bin/env python3

import unittest

from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.settings_fields import f_group


class GroupsTest(unittest.TestCase):
    def setUp(self):
        self.group1 = f_group(name="ACCESS_REGEX_HOSTNAME", device_filter={"hostname": "^.*access.*$"})
        self.group2 = f_group(name="ACCESS_ENUM_TYPE", device_filter={"device_type": "ACCESS"})
        self.group3 = f_group(name="ACCESS_DIST_REGEX_TYPE", device_filter={"device_type": "ACCESS|DIST|CORE"})
        self.group4 = f_group(name="EOS_ACCESS", device_filter={"device_type": "ACCESS", "platform": "eos"})
        self.group5 = f_group(name="IOS_DIST", device_filter={"device_type": "DIST", "platform": "ios"})
        self.group6 = f_group(name="ALL_DEVICES", devices=["access1", "access2", "dist1", "dist2"])

        self.eosaccess_device = Device(hostname="access1", platform="eos", device_type=DeviceType.ACCESS)
        self.iosaccess_device = Device(hostname="access2", platform="ios", device_type=DeviceType.ACCESS)
        self.eosdist_device = Device(hostname="dist1", platform="eos", device_type=DeviceType.DIST)
        self.iosdist_device = Device(hostname="dist2", platform="ios", device_type=DeviceType.DIST)

    def test_groups(self):
        # error when device_filter and devices are both set
        with self.assertRaises(ValueError):
            f_group(name="INVALID_GROUP", device_filter={"device_type": "ACCESS"}, devices=["access1"])

    def test_groups_device_filter_hostname(self):
        # Match on hostname
        self.assertTrue(self.group1.matches(self.eosaccess_device))
        self.assertFalse(self.group1.matches(self.eosdist_device))

        self.assertTrue(self.group1.matches(self.iosaccess_device))
        self.assertFalse(self.group1.matches(self.iosdist_device))

    def test_groups_device_filter_device_type(self):
        # Match on device type enum
        self.assertTrue(self.group2.matches(self.eosaccess_device))
        self.assertFalse(self.group2.matches(self.eosdist_device))

        self.assertTrue(self.group2.matches(self.iosaccess_device))
        self.assertFalse(self.group2.matches(self.iosdist_device))

        # Match on device type regex
        self.assertTrue(self.group3.matches(self.eosaccess_device))
        self.assertTrue(self.group3.matches(self.eosdist_device))

        self.assertTrue(self.group3.matches(self.iosaccess_device))
        self.assertTrue(self.group3.matches(self.iosdist_device))

    def test_groups_device_filter_platform(self):
        # Match on platform eos + access
        self.assertTrue(self.group4.matches(self.eosaccess_device))
        self.assertFalse(self.group4.matches(self.iosaccess_device))
        self.assertFalse(self.group4.matches(self.eosdist_device))
        self.assertFalse(self.group4.matches(self.iosdist_device))
        # Match on platform ios + dist
        self.assertTrue(self.group5.matches(self.iosdist_device))
        self.assertFalse(self.group5.matches(self.eosdist_device))
        self.assertFalse(self.group5.matches(self.eosaccess_device))
        self.assertFalse(self.group5.matches(self.iosaccess_device))

    def test_groups_device_filter_devices(self):
        # Match on device list
        self.assertTrue(self.group6.matches(self.eosaccess_device))
        self.assertTrue(self.group6.matches(self.iosaccess_device))
        self.assertTrue(self.group6.matches(self.eosdist_device))
        self.assertTrue(self.group6.matches(self.iosdist_device))

        # Check that a device not in the group does not match
        self.assertFalse(
            self.group6.matches(Device(hostname="unknown", platform="unknown", device_type=DeviceType.ACCESS))
        )
