import os
import pprint
import unittest

import pkg_resources
import pytest
import yaml

import cnaas_nms.devicehandler.get
import cnaas_nms.devicehandler.update
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.session import sqla_session


@pytest.mark.integration
class GetTests(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def requirements(self, postgresql, settings_directory):
        """Ensures the required pytest fixtures are loaded implicitly for all these tests"""
        pass

    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, "data")
        with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)

    @classmethod
    def create_test_device(cls, hostname="unittest"):
        return Device(
            ztp_mac="000000000000",
            hostname=hostname,
            platform="eos",
            management_ip=None,
            state=DeviceState.MANAGED,
            device_type=DeviceType.ACCESS,
        )

    def test_get_inventory(self):
        result = cnaas_nms.devicehandler.get.get_inventory()
        pprint.pprint(result)
        # Inventory dict should contain these top level keys
        self.assertListEqual(["hosts", "groups", "defaults"], list(result.keys()))
        # Hosts key should include atleast 1 item
        self.assertLessEqual(1, len(result["hosts"].items()))

    def test_get_mlag_ifs(self):
        with sqla_session() as session:
            try:
                dev_a: Device = self.create_test_device(self.testdata["mlag_dev_a"])
                dev_b: Device = self.create_test_device(self.testdata["mlag_dev_b"])
                dev_nonpeer: Device = self.create_test_device(self.testdata["mlag_dev_nonpeer"])
                session.add(dev_a)
                session.add(dev_b)
                session.add(dev_nonpeer)
                session.commit()
                linknets = []
                for linknet in self.testdata["linknets_mlag_peers"]:
                    linknet["device_a_hostname"] = dev_a.hostname
                    linknet["device_a_id"] = dev_a.id
                    linknet["device_b_hostname"] = dev_b.hostname
                    linknet["device_b_id"] = dev_b.id
                    linknets.append(linknet)
                for linknet in self.testdata["linknets_mlag_nonpeers"]:
                    linknet["device_a_hostname"] = dev_a.hostname
                    linknet["device_a_id"] = dev_a.id
                    linknet["device_b_hostname"] = dev_nonpeer.hostname
                    linknet["device_b_id"] = dev_nonpeer.id
                    linknets.append(linknet)

                res = cnaas_nms.devicehandler.get.get_mlag_ifs(session, dev_a, self.testdata["mlag_dev_b"], linknets)
                self.assertEqual(res, {"Ethernet25": dev_b.id, "Ethernet26": dev_b.id})
            except Exception as e:
                session.rollback()
                session.delete(dev_a)
                session.delete(dev_b)
                session.delete(dev_nonpeer)
                raise e
            else:
                session.rollback()
                session.delete(dev_a)
                session.delete(dev_b)
                session.delete(dev_nonpeer)

    @pytest.mark.equipment
    def test_update_links(self):
        with sqla_session() as session:
            new_links = cnaas_nms.devicehandler.update.update_linknets(
                session, self.testdata["init_access_new_hostname"], DeviceType.ACCESS
            )
        pprint.pprint(new_links)

    @pytest.mark.equipment
    def test_get_running_config_interface(self):
        with sqla_session() as session:
            if_config: str = cnaas_nms.devicehandler.get.get_running_config_interface(session, "eosdist1", "Ethernet1")
            assert if_config.strip(), "no config found"


if __name__ == "__main__":
    unittest.main()
