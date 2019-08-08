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
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.linknet import Linknet

from cnaas_nms.tools.testsetup import PostgresTemporaryInstance
from cnaas_nms.tools.testsetup import MongoTemporaryInstance

class DeviceTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)
        self.tmp_postgres = PostgresTemporaryInstance()
        self.tmp_mongo = MongoTemporaryInstance()

    def tearDown(self):
        self.tmp_postgres.shutdown()
        self.tmp_mongo.shutdown()

    def test_add_dist_device(self):
        with sqla_session() as session:
            #TODO: get params from testdata.yml
            new_device = Device()
            new_device.ztp_mac = '08002708a8be'
            new_device.hostname = 'eosdist'
            new_device.platform = 'eos'
            new_device.management_ip = IPv4Address('10.0.1.22')
            new_device.state = DeviceState.MANAGED
            new_device.device_type = DeviceType.DIST
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
            instance = session.query(Device).filter(Device.hostname == 'eosdist').first()
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


if __name__ == '__main__':
    unittest.main()
