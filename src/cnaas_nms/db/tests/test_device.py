#!/usr/bin/env python3

import unittest

from ipaddress import IPv4Address

from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.stackmember import Stackmember
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.session import sqla_session


class DeviceTests(unittest.TestCase):
    def cleandb(self):
        with sqla_session() as session:
            for hardware_id in ["FO64534", "FO64535"]:
                stack = session.query(Stackmember).filter(Stackmember.hardware_id == hardware_id).one_or_none()
                if stack:
                    session.delete(stack)
                    session.commit()
            for hostname in ["test-device1", "test-device2", "unittest"]:
                device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
                if device:
                    session.delete(device)
                    session.commit()

    def setUp(self):
        self.cleandb()

    def tearDown(self):
        self.cleandb()

    @classmethod
    def create_test_device(cls, hostname="unittest"):
        return Device(
            ztp_mac="08002708a8be",
            hostname=hostname,
            platform="eos",
            management_ip=IPv4Address("10.0.1.22"),
            state=DeviceState.MANAGED,
            device_type=DeviceType.DIST,
        )

    def test_get_linknets(self):
        device1 = DeviceTests.create_test_device('test-device1')
        device2 = DeviceTests.create_test_device('test-device2')
        with sqla_session() as session:
            session.add(device1)
            session.add(device2)
            test_linknet = Linknet(device_a=device1, device_b=device2)
            device1 = session.query(Device).filter(Device.hostname == 'test-device1').one()
            device2 = session.query(Device).filter(Device.hostname == 'test-device2').one()
            self.assertEquals([test_linknet], device1.get_linknets(session))
            self.assertEquals([test_linknet], device2.get_linknets(session))

    def test_get_links_to(self):
        device1 = DeviceTests.create_test_device('test-device1')
        device2 = DeviceTests.create_test_device('test-device2')
        with sqla_session() as session:
            session.add(device1)
            session.add(device2)
            test_linknet = Linknet(device_a=device1, device_b=device2)
            device1 = session.query(Device).filter(Device.hostname == 'test-device1').one()
            device2 = session.query(Device).filter(Device.hostname == 'test-device2').one()
            self.assertEquals([test_linknet], device1.get_links_to(session, device2))
            self.assertEquals([test_linknet], device2.get_links_to(session, device1))

    def test_get_neighbors(self):
        device1 = DeviceTests.create_test_device('test-device1')
        device2 = DeviceTests.create_test_device('test-device2')
        with sqla_session() as session:
            session.add(device1)
            session.add(device2)
            test_linknet = Linknet(device_a=device1, device_b=device2)
            device1 = session.query(Device).filter(Device.hostname == 'test-device1').one()
            device2 = session.query(Device).filter(Device.hostname == 'test-device2').one()
            self.assertEquals([device2], device1.get_neighbors(session))
            self.assertEquals([device1], device2.get_neighbors(session))

    def test_is_stack(self):
        with sqla_session() as session:
            new_stack = DeviceTests.create_test_device()
            session.add(new_stack)
            session.flush()
            stackmember1 = Stackmember(
                device_id = new_stack.id,
                hardware_id = "FO64534",
                member_no = "0",
            )
            session.add(stackmember1)
            self.assertTrue(new_stack.is_stack(session))
            session.delete(stackmember1)
            self.assertFalse(new_stack.is_stack(session))

    def test_get_stackmembers(self):
        with sqla_session() as session:
            new_stack = DeviceTests.create_test_device()
            session.add(new_stack)
            session.flush()
            self.assertEqual(new_stack.get_stackmembers(session), [])
            stackmember1 = Stackmember(
                device_id = new_stack.id,
                hardware_id = "FO64535",
                member_no = "0",
            )
            session.add(stackmember1)
            stackmember2 = Stackmember(
                device_id = new_stack.id,
                hardware_id = "FO64534",
                member_no = "1",
            )
            session.add(stackmember2)
            # assert the 2 lists have the same elements (regardless of ordering)
            self.assertCountEqual([stackmember1, stackmember2],
                new_stack.get_stackmembers(session))


if __name__ == '__main__':
    unittest.main()
