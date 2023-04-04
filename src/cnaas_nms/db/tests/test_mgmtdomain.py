#!/usr/bin/env python3

import os
import unittest
from ipaddress import IPv4Address, IPv4Interface, IPv4Network

import pkg_resources
import pytest
import yaml

import cnaas_nms.db.helper
from cnaas_nms.db.device import Device
from cnaas_nms.db.mgmtdomain import Mgmtdomain
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.tests.test_device import DeviceTests


@pytest.mark.integration
class MgmtdomainTests(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def requirements(self, postgresql):
        """Ensures the required pytest fixtures are loaded implicitly for all these tests"""
        pass

    @staticmethod
    def get_testdata():
        data_dir = pkg_resources.resource_filename(__name__, "data")
        with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
            return yaml.safe_load(f_testdata)

    def setUp(self):
        self.testdata = self.get_testdata()

    @classmethod
    def setUpClass(cls) -> None:
        cls.add_mgmtdomain()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.delete_mgmtdomain()

    @classmethod
    def add_mgmtdomain(cls):
        testdata = cls.get_testdata()
        with sqla_session() as session:
            d_a = DeviceTests.create_test_device("mgmtdomaintest1")
            d_b = DeviceTests.create_test_device("mgmtdomaintest2")
            session.add(d_a)
            session.add(d_b)
            new_mgmtd = Mgmtdomain()
            new_mgmtd.device_a = d_a
            new_mgmtd.device_b = d_b
            new_mgmtd.ipv4_gw = testdata["mgmtdomain_ipv4_gw"]
            new_mgmtd.vlan = testdata["mgmtdomain_vlan"]
            session.add(new_mgmtd)
            session.commit()

    @classmethod
    def delete_mgmtdomain(cls):
        with sqla_session() as session:
            d_a = session.query(Device).filter(Device.hostname == "mgmtdomaintest1").one()
            instance = session.query(Mgmtdomain).filter(Mgmtdomain.device_a == d_a).first()
            session.delete(instance)
            d_a = session.query(Device).filter(Device.hostname == "mgmtdomaintest1").one()
            d_b = session.query(Device).filter(Device.hostname == "mgmtdomaintest2").one()
            session.delete(d_a)
            session.delete(d_b)

    def test_find_mgmtdomain_invalid(self):
        with sqla_session() as session:
            self.assertRaises(ValueError, cnaas_nms.db.helper.find_mgmtdomain, session, [])
            self.assertRaises(ValueError, cnaas_nms.db.helper.find_mgmtdomain, session, [1, 2, 3])

    def test_find_mgmtdomain_twodist(self):
        with sqla_session() as session:
            mgmtdomain = cnaas_nms.db.helper.find_mgmtdomain(session, ["eosdist1", "eosdist2"])
            self.assertIsNotNone(mgmtdomain, "No mgmtdomain found for eosdist1 + eosdist2")

    def test_find_mgmtdomain_onedist(self):
        with sqla_session() as session:
            mgmtdomain = cnaas_nms.db.helper.find_mgmtdomain(session, ["eosdist1"])
            self.assertIsNotNone(mgmtdomain, "No mgmtdomain found for eosdist1")

    def test_find_mgmtdomain_oneaccess(self):
        with sqla_session() as session:
            mgmtdomain = cnaas_nms.db.helper.find_mgmtdomain(session, ["eosaccess"])
            self.assertIsNotNone(mgmtdomain, "No mgmtdomain found for eosaccess")

    def test_is_dual_stack_should_be_false_for_default_domain(self):
        with sqla_session() as session:
            mgmtdomain = session.query(Mgmtdomain).limit(1).one()
            self.assertFalse(mgmtdomain.is_dual_stack)  # domain in test data is not dual stack

    def test_primary_gw_should_be_ipv4_for_default_domain(self):
        with sqla_session() as session:
            mgmtdomain = session.query(Mgmtdomain).limit(1).one()
            self.assertEqual(mgmtdomain.ipv4_gw, mgmtdomain.primary_gw)

    def test_find_free_primary_mgmt_ip_should_return_an_ipv4_address(self):
        with sqla_session() as session:
            mgmtdomain = session.query(Mgmtdomain).limit(1).one()
            value = mgmtdomain.find_free_primary_mgmt_ip(session)
            self.assertTrue(value)
            self.assertIsInstance(value, IPv4Address)

    def test_find_free_secondary_mgmt_ip_should_return_none(self):
        with sqla_session() as session:
            mgmtdomain = session.query(Mgmtdomain).limit(1).one()
            value = mgmtdomain.find_free_secondary_mgmt_ip(session)
            self.assertIsNone(value)  # domain in test data has no secondary network

    def test_find_free_mgmt_ip(self):
        with sqla_session() as session:
            mgmtdomain = session.query(Mgmtdomain).limit(1).one()
            mgmtdomain.find_free_mgmt_ip(session)

    def test_find_free_mgmt_ip_v6(self):
        with sqla_session() as session:
            mgmtdomain = session.query(Mgmtdomain).limit(1).one()
            mgmtdomain.find_free_mgmt_ip(session, version=6)

    def test_find_free_mgmt_ip_should_fail_on_invalid_ip_version(self):
        with sqla_session() as session:
            mgmtdomain = session.query(Mgmtdomain).limit(1).one()
            with self.assertRaises(ValueError):
                mgmtdomain.find_free_mgmt_ip(session, version=42)

    def test_find_mgmtdomain_by_ip(self):
        with sqla_session() as session:
            mgmtdomain = cnaas_nms.db.helper.find_mgmtdomain_by_ip(session, IPv4Address("10.0.6.6"))
            self.assertEqual(IPv4Interface(mgmtdomain.ipv4_gw).network, IPv4Network("10.0.6.0/24"))


if __name__ == "__main__":
    unittest.main()
