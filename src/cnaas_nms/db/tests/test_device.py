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
from cnaas_nms.db.session import sqla_session, sqla_test_session
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

    def test_add_dist_device(self):
        with sqla_session() as session:
            #TODO: get params from testdata.yml
            new_device = DeviceTests.create_test_device()
            result = session.add(new_device)

        pprint.pprint(result)
        # Inventory dict should contain these top level keys
        #self.assertListEqual(
        #    ['hosts', 'groups', 'defaults'],
        #    list(result.keys()))
        # Hosts key should include atleast 1 item
        #self.assertLessEqual(
        #    1,
        #    len(result['hosts'].items()))

    def test_delete_dist_device(self):
        with sqla_session() as session:
            instance = session.query(Device).filter(Device.hostname == 'unittest').first()
            if instance:
                session.delete(instance)
                session.commit()
            else:
                print('Device not found: ')

    def test_get_device_linknets(self):
        hostname = self.testdata['query_neighbor_device']
        with sqla_session() as session:
            d = session.query(Device).filter(Device.hostname == hostname).one()
            for linknet in d.get_linknets(session):
                self.assertIsInstance(linknet, Linknet)
                pprint.pprint(linknet.as_dict())

    def test_get_device_neighbors(self):
        hostname = self.testdata['query_neighbor_device']
        with sqla_session() as session:
            d = session.query(Device).filter(Device.hostname == hostname).one()
            for nei in d.get_neighbors(session):
                self.assertIsInstance(nei, Device)
                pprint.pprint(nei.as_dict())

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
