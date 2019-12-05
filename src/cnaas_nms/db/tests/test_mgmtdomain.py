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
from cnaas_nms.db.mgmtdomain import Mgmtdomain

from cnaas_nms.tools.testsetup import PostgresTemporaryInstance

class MgmtdomainTests(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)
        self.tmp_postgres = PostgresTemporaryInstance()

    def tearDown(self):
        self.tmp_postgres.shutdown()

    def test_add_mgmt_domain(self):
        with sqla_session() as session:
            d_a = session.query(Device).filter(Device.hostname == 'eosdist').one()
            d_b = session.query(Device).filter(Device.hostname == 'eosdist2').one()
            #TODO: get params from testdata.yml
            new_mgmtd = Mgmtdomain()
            new_mgmtd.device_a = d_a
            new_mgmtd.device_b = d_b
            new_mgmtd.ipv4_gw = '10.0.6.1/24'
            new_mgmtd.vlan = 600
            result = session.add(new_mgmtd)

        pprint.pprint(result)
        # Inventory dict should contain these top level keys
        #self.assertListEqual(
        #    ['hosts', 'groups', 'defaults'],
        #    list(result.keys()))
        # Hosts key should include atleast 1 item
        #self.assertLessEqual(
        #    1,
        #    len(result['hosts'].items()))

    def test_delete_mgmt_domain(self):
        with sqla_session() as session:
            d_a = session.query(Device).filter(Device.hostname == 'eosdist').one()
            instance = session.query(Mgmtdomain).filter(Mgmtdomain.device_a == d_a).first()
            if instance:
                session.delete(instance)
                session.commit()
            else:
                print(f"Mgmtdomain for device {d_a.hostname} not found")

    def test_find_mgmt_domain(self):
        with sqla_session() as session:
            mgmtdomain = cnaas_nms.db.helper.find_mgmtdomain(session, ['eosdist', 'eosdist2'])
            if mgmtdomain:
                pprint.pprint(mgmtdomain.as_dict())

    def test_find_free_mgmt_ip(self):
        mgmtdomain_id = 2
        with sqla_session() as session:
            mgmtdomain = session.query(Mgmtdomain).filter(Mgmtdomain.id == mgmtdomain_id).one()
            if mgmtdomain:
                print(mgmtdomain.find_free_mgmt_ip(session))

if __name__ == '__main__':
    unittest.main()
