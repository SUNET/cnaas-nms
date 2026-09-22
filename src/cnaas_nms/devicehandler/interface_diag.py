"""Diagnostics for a single Junos switch port.

NAPALM's interface getter stops at link state, so the things needed to judge one
port - whether PoE delivers power, which clients dot1x authenticated, which
VLANs are really active, which MACs were learned and which DHCP leases were
handed out - are read with operational Junos commands requested in XML encoding
and parsed into the small shape the port screen renders.

A section the switch cannot answer, like PoE on a switch without it, comes back
empty instead of failing the whole read, so the rest of the port still shows.
"""

import re
from typing import Optional
from xml.etree import ElementTree

from nornir.core.exceptions import NornirSubTaskError
from nornir_napalm.plugins.tasks import napalm_cli

from cnaas_nms.db.settings_fields.shared import IFNAME_REGEX
from cnaas_nms.devicehandler.nornir_helper import cnaas_init

COMMANDS = {
    "poe": "show poe interface {ifname}",
    "dot1x": "show dot1x interface {ifname} extensive",
    "vlans": "show ethernet-switching interface {ifname}",
    "mac_addresses": "show ethernet-switching table interface {ifname}",
    "dhcp": "show dhcp-security binding interface {ifname}",
}


def _parse(output: str) -> Optional[ElementTree.Element]:
    """The command output as XML, or None when the switch answered with an error instead.

    Junos reports a refused request inside the element the reply would otherwise
    carry, so an error is found by looking for the element rather than by the
    command raising.
    """
    try:
        root = ElementTree.fromstring(output)
    except ElementTree.ParseError:
        return None
    if any(_name(element) == "error" for element in root.iter()):
        return None
    return root


def _name(element: ElementTree.Element) -> str:
    """Element name without the Junos namespace."""
    return element.tag.rpartition("}")[2]


def _elements(root: ElementTree.Element, name: str):
    return [element for element in root.iter() if _name(element) == name]


def _value(element: ElementTree.Element, name: str) -> Optional[str]:
    """Text of the direct child called name. Junos writes an absent value as "-"."""
    for child in element:
        if _name(child) == name:
            text = (child.text or "").strip()
            return text if text and text != "-" else None
    return None


def _authenticated_vlan(session: ElementTree.Element) -> Optional[str]:
    """The VLAN dot1x put the client in. Junos writes an unassigned VLAN as 0."""
    vlan = _value(session, "authenticated-vlan")
    return vlan if vlan != "0" else None


def parse_poe(output: str) -> Optional[dict]:
    root = _parse(output)
    details = _elements(root, "interface-information-detail") if root is not None else []
    if not details:
        return None
    detail = details[0]
    return {
        "enabled": _value(detail, "interface-enabled-detail") == "Enabled",
        "status": _value(detail, "interface-status-detail"),
        "status_detail": _value(detail, "interface-status-detail-extra"),
        "power": _value(detail, "interface-power-detail"),
        "power_limit": _value(detail, "interface-power-limit-detail"),
        "priority": _value(detail, "interface-priority-detail"),
        "class": _value(detail, "interface-class-detail"),
        "mode": _value(detail, "interface-mode-detail"),
    }


def parse_dot1x(output: str) -> list[dict]:
    """The dot1x entries Junos reports for the port.

    An empty list means dot1x is not configured on the port, an entry without a
    MAC means it is configured while no client has authenticated, and an entry
    with a MAC describes one client. A client that keeps retrying alternates
    between the last two, so one entry without a MAC does not prove the port is
    idle.
    """
    root = _parse(output)
    if root is None:
        return []
    return [
        {
            "mac": _value(session, "user-mac-address"),
            "username": _value(session, "user-name"),
            "state": _value(session, "state"),
            "method": _value(session, "authenticated-method"),
            "vlan": _authenticated_vlan(session),
            "voip_vlan": _value(session, "authenticated-voip-vlan"),
        }
        for session in _elements(root, "interface")
    ]


def parse_vlans(output: str) -> list[dict]:
    """The VLANs actually active on the port.

    Junos repeats the entry element for both the interface itself and each VLAN
    on it; only the ones naming a VLAN describe membership.
    """
    root = _parse(output)
    if root is None:
        return []
    entries = _elements(root, "l2ng-l2ald-iff-interface-entry")
    return [
        {
            "vlan_name": _value(entry, "l2iff-interface-vlan-name"),
            "vlan_id": _value(entry, "l2iff-interface-vlan-id"),
            "tagness": _value(entry, "l2iff-interface-vlan-member-tagness"),
            "stp_state": _value(entry, "l2iff-interface-vlan-member-stp-state"),
        }
        for entry in entries
        if _value(entry, "l2iff-interface-vlan-name")
    ]


def parse_mac_addresses(output: str) -> list[dict]:
    """MACs learned on the port. Junos groups them per VLAN, which carries the VLAN id."""
    root = _parse(output)
    if root is None:
        return []
    macs = []
    for group in _elements(root, "l2ng-l2ald-mac-entry-vlan"):
        vlan_id = _value(group, "l2ng-l2-vlan-id")
        for entry in _elements(group, "l2ng-mac-entry"):
            macs.append(
                {
                    "mac": _value(entry, "l2ng-l2-mac-address"),
                    "vlan_name": _value(entry, "l2ng-l2-mac-vlan-name"),
                    "vlan_id": vlan_id,
                    "flags": _value(entry, "l2ng-l2-mac-flags"),
                }
            )
    return macs


def parse_dhcp(output: str) -> list[dict]:
    root = _parse(output)
    if root is None:
        return []
    return [
        {
            "ip": _value(entry, "ip-address"),
            "mac": _value(entry, "hw-address"),
            "vlan_name": _value(entry, "vlan-name"),
            "lease_expiry": _value(entry, "lease-expiry"),
            "state": _value(entry, "state"),
        }
        for entry in _elements(root, "dhcp-security-entry")
    ]


PARSERS = {
    "poe": parse_poe,
    "dot1x": parse_dot1x,
    "vlans": parse_vlans,
    "mac_addresses": parse_mac_addresses,
    "dhcp": parse_dhcp,
}


def parse_interface_diag(outputs: dict[str, str]) -> dict:
    """Turn the raw command outputs into the diagnostics for one port."""
    return {section: parser(outputs[section]) for section, parser in PARSERS.items()}


def interface_diag_task(task, ifname: str) -> dict:
    if task.host.platform != "junos":
        raise ValueError(
            "Interface diagnostics is only available for junos, {} runs {}".format(task.host.name, task.host.platform)
        )
    outputs = {}
    for section, command in COMMANDS.items():
        try:
            res = task.run(
                task=napalm_cli,
                name="Get {}".format(section),
                commands=[command.format(ifname=ifname)],
                encoding="xml",
            )
        except NornirSubTaskError:
            # One section that cannot be read still leaves the others to report
            task.results[-1].failed = False
            outputs[section] = ""
        else:
            outputs[section] = next(iter(res.result.values()))
    return parse_interface_diag(outputs)


def get_interface_diag(hostname: str, ifname: str) -> dict:
    if not re.fullmatch(IFNAME_REGEX, ifname):
        raise ValueError(f"Invalid interface name {ifname}")
    nr = cnaas_init()
    nr_filtered = nr.filter(name=hostname).filter(managed=True)
    if len(nr_filtered.inventory) != 1:
        raise ValueError(f"Hostname {hostname} not found in inventory")
    nrresult = nr_filtered.run(task=interface_diag_task, ifname=ifname)
    if nrresult.failed or nrresult[hostname].failed:
        raise Exception(
            "Could not get interface diagnostics for {} {}: {}".format(hostname, ifname, nrresult[hostname].exception)
        )
    return nrresult[hostname][0].result
