#!/usr/bin/env python3

import sys
import unittest
import pkg_resources
import yaml
import os
import pprint

from ipaddress import IPv4Address

import cnaas_nms.db.helper
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.stackmember import Stackmember
from cnaas_nms.db.session import sqla_test_session
from cnaas_nms.db.linknet import Linknet

from cnaas_nms.tools.testsetup import PostgresTemporaryInstance

class DeviceTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)
        self.tmp_postgres = PostgresTemporaryInstance()

    def tearDown(self):
        self.tmp_postgres.shutdown()

    def create_test_device(hostname="unittest"):
        return Device(
            ztp_mac="08002708a8be",
            hostname=hostname,
            platform="eos",
            management_ip=IPv4Address("10.0.1.22"),
            state=DeviceState.MANAGED,
            device_type=DeviceType.DIST,
        )

    def test_add_and_delete_dist_device(self):
        new_device = DeviceTests.create_test_device()
        with sqla_test_session() as session:
            session.add(new_device)
            instance = session.query(Device).filter(Device.hostname == 'unittest').first()
            self.assertEquals(instance, new_device)
            session.delete(instance)
            deleted_instance = session.query(Device).filter(Device.hostname == 'unittest').first()
            self.assertIsNone(deleted_instance)

    def test_get_device_linknets(self):
        device1 = DeviceTests.create_test_device('test-device1')
        device2 = DeviceTests.create_test_device('test-device2')
        with sqla_test_session() as session:
            session.add(device1)
            session.add(device2)
            test_linknet = Linknet(
                device_a = device1,
                device_b = device2
            )
            d = session.query(Device).filter(Device.hostname == 'test-device1').one()
            n = session.query(Device).filter(Device.hostname == 'test-device2').one()
            self.assertTrue(d.get_linknets(session))   # list is not empty
            self.assertTrue(n.get_linknets(session))
            for linknet in d.get_linknets(session):
                self.assertIsInstance(linknet, Linknet)
            self.assertEquals([test_linknet], d.get_linknets(session))
            self.assertEquals([test_linknet], n.get_linknets(session))

    def test_get_device_neighbors(self):
        new_device = DeviceTests.create_test_device('testdevice')
        neighbour_device = DeviceTests.create_test_device('neighbourdevice')
        with sqla_test_session() as session:
            session.add(new_device)
            session.add(neighbour_device)
            test_linknet = Linknet(
                device_a = new_device,
                device_b = neighbour_device
            )
            # check neighbour relation one way
            d = session.query(Device).filter(Device.hostname == 'testdevice').one()
            self.assertEquals([neighbour_device], d.get_neighbors(session))
            # check the other way
            n = session.query(Device).filter(Device.hostname == 'neighbourdevice').one()
            self.assertEquals([new_device], n.get_neighbors(session))
            # check type
            for nei in d.get_neighbors(session):
                self.assertIsInstance(nei, Device)

    def test_add_stackmember(self):
        with sqla_test_session() as session:
            new_stack = DeviceTests.create_test_device('unittest2')
            session.add(new_stack)
            session.flush()

            stackmember1 = Stackmember(
                device_id = new_stack.id,
                hardware_id = "DHWAJDJWADDWADWA",
                member_no = "1",
                priority = "1",
            )
            session.add(stackmember1)
            session.flush()

            self.assertEquals(stackmember1,
                session.query(Stackmember).filter(Stackmember.device == new_stack).one())

    def test_is_stack(self):
        with sqla_test_session() as session:
            new_stack = DeviceTests.create_test_device('unittest3')
            session.add(new_stack)
            session.flush()

            stackmember1 = Stackmember(
                device_id = new_stack.id,
                hardware_id = "DHWAJDJWADDWADWB",
                member_no = "1",
            )
            session.add(stackmember1)
            session.flush()

            self.assertTrue(new_stack.is_stack(session))

            session.delete(stackmember1)
            self.assertFalse(new_stack.is_stack(session))

    def test_get_stackmembers(self):
        with sqla_test_session() as session:
            new_stack = DeviceTests.create_test_device('unittest4')
            session.add(new_stack)
            session.flush()
            self.assertIsNone(new_stack.get_stackmembers(session))

            stackmember1 = Stackmember(
                device_id = new_stack.id,
                hardware_id = "DHWAJDJWADDWADWC",
                member_no = "0",
            )
            session.add(stackmember1)
            stackmember2 = Stackmember(
                device_id = new_stack.id,
                hardware_id = "DHWAJDJWADDWADWD",
                member_no = "1",
            )
            session.add(stackmember2)
            session.flush()

            # lists have same elements, regardless of ordering
            self.assertCountEqual([stackmember1, stackmember2],
                new_stack.get_stackmembers(session))

if __name__ == '__main__':
    unittest.main()
