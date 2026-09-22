import pytest

from cnaas_nms.devicehandler.interface_diag import parse_interface_diag

# Command output requested with XML encoding, as NAPALM hands it back for one
# command. The structure is recorded from real switches, an EX running Junos 24.4
# for the samples below and EX4100s for the ones further down, with MAC
# addresses, user names, addresses and site-specific VLAN names replaced by
# synthetic values of the same shape.

POE_XML = """
<rpc-reply xmlns:junos="http://xml.juniper.net/junos/24.4R2-S4.10/junos">
    <poe>
        <interface-information-detail>
            <interface-name-detail>mge-0/0/0</interface-name-detail>
            <interface-enabled-detail>Enabled</interface-enabled-detail>
            <interface-status-detail>ON</interface-status-detail>
            <interface-status-detail-extra>4P Port delivering 4P IEEE SSPD</interface-status-detail-extra>
            <interface-fourpair-enabled-detail>Disabled</interface-fourpair-enabled-detail>
            <interface-power-limit-detail>25.0W</interface-power-limit-detail>
            <interface-lldp-negotiation-power-detail>(L)</interface-lldp-negotiation-power-detail>
            <interface-priority-detail>Low</interface-priority-detail>
            <interface-lldp-negotiation-priority-detail>   </interface-lldp-negotiation-priority-detail>
            <interface-power-detail>11.4W</interface-power-detail>
            <interface-detail-asterisk> </interface-detail-asterisk>
            <interface-class-detail>5/-</interface-class-detail>
            <interface-mode-detail>802.3bt</interface-mode-detail>
        </interface-information-detail>
        <poe-error>
            <poe-lldp-negotiation-value-interface/>
        </poe-error>
    </poe>
    <cli>
        <banner>{master:0}</banner>
    </cli>
</rpc-reply>
"""

DOT1X_XML = """
<rpc-reply xmlns:junos="http://xml.juniper.net/junos/24.4R2-S4.10/junos">
    <dot1x-interface-information>
        <interface junos:style="extensive">
            <interface-name>ge-0/0/27.0</interface-name>
            <user-mac-address>00:00:5E:00:53:0A</user-mac-address>
            <authenticated-method>Mac Radius</authenticated-method>
            <authenticated-vlan>630</authenticated-vlan>
            <authenticated-voip-vlan>-</authenticated-voip-vlan>
            <user-name>00005e00530a</user-name>
            <state>Authenticated</state>
        </interface>
        <interface junos:style="extensive">
            <interface-name>ge-0/0/27.0</interface-name>
            <user-mac-address>00:00:5E:00:53:0B</user-mac-address>
            <authenticated-method>Radius</authenticated-method>
            <authenticated-vlan>208</authenticated-vlan>
            <authenticated-voip-vlan>-</authenticated-voip-vlan>
            <user-name>host/DSK-EXAMPLE0001</user-name>
            <state>Authenticated</state>
        </interface>
    </dot1x-interface-information>
    <cli>
        <banner>{master:0}</banner>
    </cli>
</rpc-reply>
"""

VLANS_XML = """
<rpc-reply xmlns:junos="http://xml.juniper.net/junos/24.4R2-S4.10/junos">
    <l2ng-l2ald-iff-interface-information xmlns="http://xml.juniper.net/junos/24.4R0/junos-l2al">
        <l2ng-l2ald-iff-interface-entry junos:style="brief">
            <l2iff-interface-lr-name></l2iff-interface-lr-name>
            <l2iff-interface-rtt-name>default-switch</l2iff-interface-rtt-name>
            <l2ng-l2ald-iff-interface-entry junos:style="brief">
                <l2iff-interface-name>mge-0/0/0.0</l2iff-interface-name>
                <l2iff-interface-vlan-name/>
                <l2iff-interface-mac-limit>65536</l2iff-interface-mac-limit>
                <l2iff-interface-mac-ip-limit>0</l2iff-interface-mac-ip-limit>
                <l2iff-interface-vlan-member-stp-state/>
                <l2iff-interface-flags></l2iff-interface-flags>
                <l2iff-interface-vlan-member-tagness>tagged,untagged</l2iff-interface-vlan-member-tagness>
            </l2ng-l2ald-iff-interface-entry>
            <l2ng-l2ald-iff-interface-entry junos:style="brief">
                <l2iff-interface-name/>
                <l2iff-interface-vlan-name>default</l2iff-interface-vlan-name>
                <l2iff-interface-vlan-id>1</l2iff-interface-vlan-id>
                <l2iff-interface-vlan-member-tagness>untagged</l2iff-interface-vlan-member-tagness>
                <l2iff-interface-mac-limit>65536</l2iff-interface-mac-limit>
                <l2iff-interface-mac-ip-limit>0</l2iff-interface-mac-ip-limit>
                <l2iff-interface-vlan-member-stp-state>Forwarding</l2iff-interface-vlan-member-stp-state>
                <l2iff-interface-flags></l2iff-interface-flags>
            </l2ng-l2ald-iff-interface-entry>
            <l2ng-l2ald-iff-interface-entry junos:style="brief">
                <l2iff-interface-name/>
                <l2iff-interface-vlan-name>WIFI-AP</l2iff-interface-vlan-name>
                <l2iff-interface-vlan-id>780</l2iff-interface-vlan-id>
                <l2iff-interface-vlan-member-tagness>untagged</l2iff-interface-vlan-member-tagness>
                <l2iff-interface-mac-limit>65536</l2iff-interface-mac-limit>
                <l2iff-interface-mac-ip-limit>0</l2iff-interface-mac-ip-limit>
                <l2iff-interface-vlan-member-stp-state>Forwarding</l2iff-interface-vlan-member-stp-state>
                <l2iff-interface-flags></l2iff-interface-flags>
            </l2ng-l2ald-iff-interface-entry>
        </l2ng-l2ald-iff-interface-entry>
    </l2ng-l2ald-iff-interface-information>
    <cli>
        <banner>{master:0}</banner>
    </cli>
</rpc-reply>
"""

MAC_XML = """
<rpc-reply xmlns:junos="http://xml.juniper.net/junos/24.4R2-S4.10/junos">
    <l2ng-l2ald-interface-macdb-vlan>
        <l2ng-l2ald-macdb-if-name>mge-0/0/0</l2ng-l2ald-macdb-if-name>
        <l2ng-l2ald-macdb-if-name>mge-0/0/0.0</l2ng-l2ald-macdb-if-name>
        <l2ng-l2ald-mac-entry-vlan junos:style="brief-rtb">
            <mac-count-global>1</mac-count-global>
            <learnt-mac-count>1</learnt-mac-count>
            <l2ng-l2-mac-routing-instance>default-switch</l2ng-l2-mac-routing-instance>
            <l2ng-l2-vlan-id>780</l2ng-l2-vlan-id>
            <l2ng-mac-entry>
                <l2ng-l2-mac-vlan-name>WIFI-AP</l2ng-l2-mac-vlan-name>
                <l2ng-l2-mac-address>00:00:5e:00:53:0d</l2ng-l2-mac-address>
                <l2ng-l2-mac-flags>D</l2ng-l2-mac-flags>
                <l2ng-l2-mac-age>-</l2ng-l2-mac-age>
                <l2ng-l2-mac-logical-interface>mge-0/0/0.0</l2ng-l2-mac-logical-interface>
                <l2ng-l2-mac-fwd-next-hop>0</l2ng-l2-mac-fwd-next-hop>
                <l2ng-l2-mac-rtr-id>0</l2ng-l2-mac-rtr-id>
            </l2ng-mac-entry>
        </l2ng-l2ald-mac-entry-vlan>
    </l2ng-l2ald-interface-macdb-vlan>
    <cli>
        <banner>{master:0}</banner>
    </cli>
</rpc-reply>
"""

DHCP_XML = """
<rpc-reply xmlns:junos="http://xml.juniper.net/junos/24.4R2-S4.10/junos">
    <dhcp-security-binding junos:style="summary">
        <dhcp-security-entries>
            <dhcp-security-entry>
                <ip-address>192.0.2.215</ip-address>
                <hw-address>00:00:5e:00:53:0b</hw-address>
                <vlan-name>OFFICE-RESERVED</vlan-name>
                <lease-expiry>84209</lease-expiry>
                <state>BOUND</state>
                <intf-name>ge-0/0/27.0</intf-name>
            </dhcp-security-entry>
            <dhcp-security-entry>
                <ip-address>10.20.30.74</ip-address>
                <hw-address>00:00:5e:00:53:0a</hw-address>
                <vlan-name>VOICE</vlan-name>
                <lease-expiry>447740</lease-expiry>
                <state>BOUND</state>
                <intf-name>ge-0/0/27.0</intf-name>
            </dhcp-security-entry>
        </dhcp-security-entries>
    </dhcp-security-binding>
    <cli>
        <banner>{master:0}</banner>
    </cli>
</rpc-reply>
"""


POE_NOT_SUPPORTED_XML = """
<rpc-reply>
    <poe>
        <interface-information-detail>
            <error>
                <parse/>
                <source-daemon>chassisd</source-daemon>
                <message>error: PoE is not supported on interface ae0</message>
            </error>
        </interface-information-detail>
    </poe>
</rpc-reply>
"""

# The same reply as POE_XML for a port whose PoE is switched off in the
# configuration. Junos reports that as "Disabled" in both the administrative and
# the operational status, where "OFF" means PoE is on but nothing is drawing
# power.
POE_DISABLED_XML = POE_XML.replace(
    "<interface-enabled-detail>Enabled</interface-enabled-detail>",
    "<interface-enabled-detail>Disabled</interface-enabled-detail>",
).replace(
    "<interface-status-detail>ON</interface-status-detail>",
    "<interface-status-detail>Disabled</interface-status-detail>",
)

# A port that is on but has nothing plugged into it, recorded from an EX4100.
POE_IDLE_XML = POE_XML.replace(
    "<interface-status-detail>ON</interface-status-detail>", "<interface-status-detail>OFF</interface-status-detail>"
).replace(
    "<interface-status-detail-extra>4P Port delivering 4P IEEE SSPD</interface-status-detail-extra>",
    "<interface-status-detail-extra>Detection In Progress</interface-status-detail-extra>",
)

DOT1X_FAILING_XML = """
<rpc-reply>
    <dot1x-interface-information>
        <interface style="extensive">
            <interface-name>mge-0/0/0.0</interface-name>
            <user-mac-address>00:00:5E:00:53:0C</user-mac-address>
            <authenticated-method>Fail</authenticated-method>
            <authenticated-vlan>0</authenticated-vlan>
            <authenticated-voip-vlan>-</authenticated-voip-vlan>
            <user-name>00005e00530c</user-name>
            <state>Connecting</state>
        </interface>
    </dot1x-interface-information>
</rpc-reply>
"""

DOT1X_NO_CLIENT_XML = """
<rpc-reply>
    <dot1x-interface-information>
        <interface style="extensive">
            <interface-name>ge-0/0/16.0</interface-name>
            <state>Initialize</state>
        </interface>
    </dot1x-interface-information>
</rpc-reply>
"""

MAC_LAG_XML = """
<rpc-reply>
    <l2ng-l2ald-interface-macdb-vlan>
        <l2ng-l2ald-macdb-if-name>ae0</l2ng-l2ald-macdb-if-name>
        <l2ng-l2ald-macdb-if-name>ae0.0</l2ng-l2ald-macdb-if-name>
        <l2ng-l2ald-mac-entry-vlan style="brief-rtb">
            <mac-count-global>2</mac-count-global>
            <learnt-mac-count>2</learnt-mac-count>
            <l2ng-l2-mac-routing-instance>default-switch</l2ng-l2-mac-routing-instance>
            <l2ng-l2-vlan-id>3</l2ng-l2-vlan-id>
            <l2ng-mac-entry>
                <l2ng-l2-mac-vlan-name>MGMT</l2ng-l2-mac-vlan-name>
                <l2ng-l2-mac-address>00:00:5e:00:53:01</l2ng-l2-mac-address>
                <l2ng-l2-mac-flags>D</l2ng-l2-mac-flags>
                <l2ng-l2-mac-age>-</l2ng-l2-mac-age>
                <l2ng-l2-mac-logical-interface>ae0.0</l2ng-l2-mac-logical-interface>
                <l2ng-l2-mac-fwd-next-hop>0</l2ng-l2-mac-fwd-next-hop>
                <l2ng-l2-mac-rtr-id>0</l2ng-l2-mac-rtr-id>
            </l2ng-mac-entry>
            <l2ng-mac-entry>
                <l2ng-l2-mac-vlan-name>MGMT</l2ng-l2-mac-vlan-name>
                <l2ng-l2-mac-address>00:00:5e:00:53:0e</l2ng-l2-mac-address>
                <l2ng-l2-mac-flags>D</l2ng-l2-mac-flags>
                <l2ng-l2-mac-age>-</l2ng-l2-mac-age>
                <l2ng-l2-mac-logical-interface>ae0.0</l2ng-l2-mac-logical-interface>
                <l2ng-l2-mac-fwd-next-hop>0</l2ng-l2-mac-fwd-next-hop>
                <l2ng-l2-mac-rtr-id>0</l2ng-l2-mac-rtr-id>
            </l2ng-mac-entry>
        </l2ng-l2ald-mac-entry-vlan>
    </l2ng-l2ald-interface-macdb-vlan>
</rpc-reply>
"""

UNKNOWN_INTERFACE_OUTPUTS = {
    "poe": """
<rpc-reply>
        <poe>
                <interface-information-detail>
                        <error>
                                <parse/>
                                <source-daemon>chassisd</source-daemon>
                                <message>error: PoE is not supported on interface ae99</message>
                        </error>
                </interface-information-detail>
        </poe>
</rpc-reply>
""",
    "dot1x": """
<rpc-reply>
        <dot1x-interface-information>
</dot1x-interface-information>
</rpc-reply>
""",
    "vlans": """
<rpc-reply>
        <l2ng-l2ald-iff-interface-information>
</l2ng-l2ald-iff-interface-information>
</rpc-reply>
""",
    "mac_addresses": """
<rpc-reply>
        <l2ng-l2ald-interface-macdb-vlan>
</l2ng-l2ald-interface-macdb-vlan>
</rpc-reply>
""",
    "dhcp": """
<rpc-reply>
        <dhcp-security-binding style="summary">
</dhcp-security-binding>
</rpc-reply>
""",
}


@pytest.fixture
def outputs():
    return {
        "poe": POE_XML,
        "dot1x": DOT1X_XML,
        "vlans": VLANS_XML,
        "mac_addresses": MAC_XML,
        "dhcp": DHCP_XML,
    }


def test_poe_shows_whether_the_port_delivers_power_and_how_much(outputs):
    poe = parse_interface_diag(outputs)["poe"]

    assert poe["enabled"] is True
    assert poe["status"] == "ON"
    assert poe["power"] == "11.4W"
    assert poe["power_limit"] == "25.0W"
    assert poe["priority"] == "Low"
    assert poe["class"] == "5/-"
    assert poe["mode"] == "802.3bt"


def test_poe_is_absent_when_the_switch_has_no_poe_on_that_port(outputs):
    outputs["poe"] = POE_NOT_SUPPORTED_XML

    diag = parse_interface_diag(outputs)

    assert diag["poe"] is None
    # a port without PoE must still report everything else
    assert diag["dot1x"] and diag["vlans"] and diag["mac_addresses"]


def test_dot1x_lists_every_authenticated_client_on_the_port(outputs):
    sessions = parse_interface_diag(outputs)["dot1x"]

    assert [s["mac"] for s in sessions] == ["00:00:5E:00:53:0A", "00:00:5E:00:53:0B"]
    assert [s["username"] for s in sessions] == ["00005e00530a", "host/DSK-EXAMPLE0001"]
    assert [s["vlan"] for s in sessions] == ["630", "208"]
    assert [s["method"] for s in sessions] == ["Mac Radius", "Radius"]
    assert all(s["state"] == "Authenticated" for s in sessions)


def test_dot1x_reports_no_voice_vlan_as_empty_rather_than_a_dash(outputs):
    sessions = parse_interface_diag(outputs)["dot1x"]

    assert all(s["voip_vlan"] is None for s in sessions)


def test_effective_vlans_are_the_ones_actually_active_on_the_port(outputs):
    vlans = parse_interface_diag(outputs)["vlans"]

    assert [(v["vlan_name"], v["vlan_id"]) for v in vlans] == [("default", "1"), ("WIFI-AP", "780")]
    assert all(v["tagness"] == "untagged" for v in vlans)
    assert all(v["stp_state"] == "Forwarding" for v in vlans)


def test_mac_table_lists_learned_macs_with_the_vlan_they_were_learned_in(outputs):
    macs = parse_interface_diag(outputs)["mac_addresses"]

    assert macs == [
        {
            "mac": "00:00:5e:00:53:0d",
            "vlan_name": "WIFI-AP",
            "vlan_id": "780",
            "flags": "D",
        }
    ]


def test_dhcp_shows_which_ip_each_client_on_the_port_was_given(outputs):
    leases = parse_interface_diag(outputs)["dhcp"]

    assert [lease["ip"] for lease in leases] == ["192.0.2.215", "10.20.30.74"]
    assert [lease["mac"] for lease in leases] == ["00:00:5e:00:53:0b", "00:00:5e:00:53:0a"]
    assert [lease["vlan_name"] for lease in leases] == ["OFFICE-RESERVED", "VOICE"]
    assert [lease["lease_expiry"] for lease in leases] == ["84209", "447740"]
    assert all(lease["state"] == "BOUND" for lease in leases)


def test_a_quiet_port_reports_empty_sections_instead_of_failing():
    empty = "<rpc-reply><cli><banner>{master:0}</banner></cli></rpc-reply>"

    diag = parse_interface_diag(dict.fromkeys(["poe", "dot1x", "vlans", "mac_addresses", "dhcp"], empty))

    assert diag == {"poe": None, "dot1x": [], "vlans": [], "mac_addresses": [], "dhcp": []}


def test_dot1x_still_names_the_client_while_authentication_keeps_failing(outputs):
    outputs["dot1x"] = DOT1X_FAILING_XML

    sessions = parse_interface_diag(outputs)["dot1x"]

    assert [s["mac"] for s in sessions] == ["00:00:5E:00:53:0C"]
    assert [s["username"] for s in sessions] == ["00005e00530c"]
    assert [s["state"] for s in sessions] == ["Connecting"]
    assert [s["method"] for s in sessions] == ["Fail"]
    # dot1x has not put the client in a VLAN, which Junos writes as 0
    assert [s["vlan"] for s in sessions] == [None]


def test_mac_table_of_an_aggregate_lists_the_macs_learned_behind_it(outputs):
    outputs["mac_addresses"] = MAC_LAG_XML

    macs = parse_interface_diag(outputs)["mac_addresses"]

    assert [mac["mac"] for mac in macs] == ["00:00:5e:00:53:01", "00:00:5e:00:53:0e"]
    assert all(mac["vlan_name"] == "MGMT" for mac in macs)
    assert all(mac["vlan_id"] == "3" for mac in macs)


def test_an_unknown_interface_reports_empty_sections_instead_of_failing():
    diag = parse_interface_diag(UNKNOWN_INTERFACE_OUTPUTS)

    assert diag == {"poe": None, "dot1x": [], "vlans": [], "mac_addresses": [], "dhcp": []}


def test_dot1x_configured_without_a_client_is_not_reported_as_a_session(outputs):
    outputs["dot1x"] = DOT1X_NO_CLIENT_XML

    sessions = parse_interface_diag(outputs)["dot1x"]

    assert [s["mac"] for s in sessions] == [None]
    assert [s["state"] for s in sessions] == ["Initialize"]


def test_poe_switched_off_in_the_configuration_is_not_reported_as_enabled(outputs):
    # A port whose PoE is administratively off is why an access point gets no
    # power, so it must not read the same as one that is on.
    outputs["poe"] = POE_DISABLED_XML

    poe = parse_interface_diag(outputs)["poe"]

    assert poe["enabled"] is False
    assert poe["status"] == "Disabled"


def test_poe_that_is_on_but_idle_is_told_apart_from_poe_that_is_switched_off(outputs):
    # Both deliver no power, and only the first will start doing so when a
    # device is plugged in, so a port waiting for one must not read as disabled.
    outputs["poe"] = POE_IDLE_XML

    poe = parse_interface_diag(outputs)["poe"]

    assert poe["enabled"] is True
    assert poe["status"] == "OFF"


def test_a_command_that_failed_leaves_its_section_empty_and_the_others_intact():
    # A section whose command could not be run reaches the parser as empty
    # output. That section reports nothing while the rest of the port still
    # does, rather than the whole read failing.
    outputs = {
        "poe": POE_XML,
        "dot1x": "",
        "vlans": VLANS_XML,
        "mac_addresses": MAC_XML,
        "dhcp": DHCP_XML,
    }

    diag = parse_interface_diag(outputs)

    assert diag["dot1x"] == []
    assert diag["poe"] is not None
    assert diag["vlans"] and diag["mac_addresses"] and diag["dhcp"]


def test_a_port_without_dot1x_reports_no_entries_at_all(outputs):
    outputs["dot1x"] = UNKNOWN_INTERFACE_OUTPUTS["dot1x"]

    assert parse_interface_diag(outputs)["dot1x"] == []
