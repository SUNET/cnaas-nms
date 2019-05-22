#!/usr/bin/env python3

import sys
import unittest
import pkg_resources
import yaml
import os
import pprint
import cnaas_nms.db.helper

from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.groups import Groups, DeviceGroups


class GroupsTest(unittest.TestCase):
    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)

    def test_add_group(self):
        with sqla_session() as session:
            new_group = Groups()
            new_group.name = 'Foo'
            new_group.description = 'Bar'
            result = session.add(new_group)
            session.commit()
            
    def test_delete_group(self):
        with sqla_session() as session:
            instance = session.query(Groups).filter(Groups.name == 'Foo').first()
            if instance:
                session.delete(instance)
                session.commit()
            else:
                print('Device not found: ')
        
