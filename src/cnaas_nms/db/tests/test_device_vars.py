import copy
import logging
import os

import pkg_resources
import pytest
import yaml

from cnaas_nms.db.device_vars import expand_interface_settings


@pytest.fixture
def testdata(scope="session"):
    data_dir = pkg_resources.resource_filename(__name__, "data")
    with open(os.path.join(data_dir, "testdata.yml"), "r") as f_testdata:
        return yaml.safe_load(f_testdata)


def test_expand_interface_settings_norange(testdata):
    iflist = []
    for i in range(1, 5):
        ifdict_new = copy.deepcopy(testdata["settings_ifdict"])
        ifdict_new["name"] = "Ethernet{}".format(i)
        iflist.append(ifdict_new)

    expanded = expand_interface_settings(iflist)
    assert expanded == iflist


def test_expand_interface_settings_range(testdata, caplog):
    iflist = []
    for i in range(1, 5):
        ifdict_new = copy.deepcopy(testdata["settings_ifdict"])
        ifdict_new["name"] = "Ethernet{}".format(i)
        iflist.append(ifdict_new)

    if_range = copy.deepcopy(testdata["settings_ifdict"])
    if_range["name"] = "Ethernet[1-4]"

    expanded = sorted(expand_interface_settings(iflist), key=lambda d: d["name"])
    with caplog.at_level(logging.DEBUG):
        expanded_range = sorted(expand_interface_settings([if_range]), key=lambda d: d["name"])
    assert expanded == expanded_range
    assert "Expanding interface range" in caplog.text
