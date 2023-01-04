import os
import unittest
from typing import Optional

import pkg_resources
import pytest
import yaml

from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.interface import InterfaceError
from cnaas_nms.db.session import sqla_session
from cnaas_nms.devicehandler.init_device import InitVerificationError, pre_init_check_neighbors
from cnaas_nms.devicehandler.update import update_linknets


@pytest.mark.integration
class UpdateTests(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def requirements(self, postgresql, settings_directory):
        """Ensures the required pytest fixtures are loaded implicitly for all these tests"""
        pass

    def setUp(self):
        data_dir = pkg_resources.resource_filename(__name__, "data")
        with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)

    def get_linknets(self, session, neighbors_data: Optional[dict] = None, hostname: str = "eosaccess"):
        if not neighbors_data:
            neighbors_data = self.testdata["lldp_data_redundant"]
        return update_linknets(
            session,
            hostname=hostname,
            devtype=DeviceType.ACCESS,
            ztp_hostname=hostname,
            dry_run=True,
            neighbors_arg=neighbors_data,
        )

    def test_update_linknet_eosaccess(self):
        with sqla_session() as session:
            linknets = self.get_linknets(session)
            for ln in linknets:
                ln["device_a_id"] = None
                ln["device_b_id"] = None
            self.assertListEqual(
                linknets,
                self.testdata["linknet_redundant"],
                "Update linknets returned unexpected data for eosaccess links",
            )

    def test_update_linknet_eosaccess_nonredundant(self):
        with sqla_session() as session:
            linknets = self.get_linknets(session, self.testdata["lldp_data_nonredundant"])
            for ln in linknets:
                ln["device_a_id"] = None
                ln["device_b_id"] = None
            self.assertListEqual(
                linknets,
                self.testdata["linknet_nonredundant"],
                "Update linknets returned unexpected data for eosaccess links",
            )

    def test_update_linknet_wrong_porttype(self):
        with sqla_session() as session:
            neighbors_data = {
                "Ethernet2": [{"hostname": "eosdist1", "port": "Ethernet1"}],
                "Ethernet3": [{"hostname": "eosdist2", "port": "Ethernet1"}],
            }
            self.assertRaises(
                InterfaceError,
                update_linknets,
                session,
                hostname="eosaccess",
                devtype=DeviceType.ACCESS,
                ztp_hostname="eosaccess",
                dry_run=True,
                neighbors_arg=neighbors_data,
            )

    def test_pre_init_check_access_redundant(self):
        with sqla_session() as session:
            linknets = self.get_linknets(session)
            dev: Device = session.query(Device).filter(Device.hostname == "eosaccess").one()
            self.assertListEqual(
                pre_init_check_neighbors(session, dev, DeviceType.ACCESS, linknets), ["eosdist1", "eosdist2"]
            )

    def test_pre_init_check_access_nonredundant(self):
        with sqla_session() as session:
            linknets = self.get_linknets(session, self.testdata["lldp_data_nonredundant"])
            dev: Device = session.query(Device).filter(Device.hostname == "eosaccess").one()
            self.assertListEqual(pre_init_check_neighbors(session, dev, DeviceType.ACCESS, linknets), ["eosdist1"])

    def test_pre_init_check_access_nonredundant_error(self):
        with sqla_session() as session:
            linknets = self.get_linknets(session, self.testdata["lldp_data_nonredundant_error"])
            dev: Device = session.query(Device).filter(Device.hostname == "eosaccess").one()
            self.assertRaises(
                InitVerificationError, pre_init_check_neighbors, session, dev, DeviceType.ACCESS, linknets
            )


if __name__ == "__main__":
    unittest.main()
