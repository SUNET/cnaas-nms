import pytest
from pydantic import ValidationError

from cnaas_nms.db.settings import f_root

TEXT_THAT_BREAKS_DEVICE_CONFIG = [
    'Room "B1.23"',
    "C:\\temp\\",
    # Every character str.splitlines() splits on
    *(f"uplink{c}" for c in "\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029"),
]

SETTINGS_WITH_TEXT = {
    "interface description": lambda text: {
        "interfaces": [{"name": "Ethernet1", "ifclass": "custom", "description": text}]
    },
    "vxlan description": lambda text: {
        "vxlans": {"student": {"vni": 100100, "vlan_id": 100, "vlan_name": "STUDENT", "description": text}}
    },
    "bgp neighbor_v4 description": lambda text: {
        "extroute_bgp": {
            "vrfs": [
                {
                    "name": "OUTSIDE",
                    "local_as": 64512,
                    "neighbor_v4": [
                        {
                            "peer_ipv4": "192.0.2.1",
                            "peer_as": 64513,
                            "route_map_in": "IN",
                            "route_map_out": "OUT",
                            "description": text,
                        }
                    ],
                }
            ]
        }
    },
    "bgp neighbor_v6 description": lambda text: {
        "extroute_bgp": {
            "vrfs": [
                {
                    "name": "OUTSIDE",
                    "local_as": 64512,
                    "neighbor_v6": [
                        {
                            "peer_ipv6": "2001:db8::1",
                            "peer_as": 64513,
                            "route_map_in": "IN",
                            "route_map_out": "OUT",
                            "description": text,
                        }
                    ],
                }
            ]
        }
    },
}

SETTINGS_WITH_WORD = {
    "static route ipv4 name": lambda word: {
        "extroute_static": {
            "vrfs": [
                {"name": "OUTSIDE", "ipv4": [{"destination": "198.51.100.0/24", "nexthop": "192.0.2.1", "name": word}]}
            ]
        }
    },
    "static route ipv6 name": lambda word: {
        "extroute_static": {
            "vrfs": [
                {
                    "name": "OUTSIDE",
                    "ipv6": [{"destination": "2001:db8:1::/48", "nexthop": "2001:db8::1", "name": word}],
                }
            ]
        }
    },
}

SETTINGS_WITH_TEXT_OR_WORD = SETTINGS_WITH_TEXT | SETTINGS_WITH_WORD


@pytest.mark.parametrize("text", TEXT_THAT_BREAKS_DEVICE_CONFIG)
@pytest.mark.parametrize("settings", SETTINGS_WITH_TEXT_OR_WORD.values(), ids=SETTINGS_WITH_TEXT_OR_WORD.keys())
def test_text_that_breaks_device_config_is_rejected(settings, text):
    invalid_settings = settings(text)
    with pytest.raises(ValidationError):
        f_root.model_validate(invalid_settings)


@pytest.mark.parametrize("word", ["to firewall", ""])
@pytest.mark.parametrize("settings", SETTINGS_WITH_WORD.values(), ids=SETTINGS_WITH_WORD.keys())
def test_name_that_is_not_one_word_is_rejected(settings, word):
    invalid_settings = settings(word)
    with pytest.raises(ValidationError):
        f_root.model_validate(invalid_settings)


@pytest.mark.parametrize("settings", SETTINGS_WITH_TEXT.values(), ids=SETTINGS_WITH_TEXT.keys())
def test_ordinary_text_is_accepted(settings):
    f_root.model_validate(settings("Västerås B1.23 - AP's & printers (2nd floor)"))


@pytest.mark.parametrize("settings", SETTINGS_WITH_WORD.values(), ids=SETTINGS_WITH_WORD.keys())
def test_ordinary_name_is_accepted(settings):
    f_root.model_validate(settings("to-FW_B1.23"))
