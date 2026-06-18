from enum import StrEnum, auto
from ipaddress import AddressValueError, IPv4Interface
from typing import Annotated

from pydantic import Field

# HOSTNAME_REGEX = r'([a-z0-9-]{1,63}\.?)+'
IPV4_REGEX = r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}" r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
# IPv6 regex from https://stackoverflow.com/questions/53497/regular-expression-that-matches-valid-ipv6-addresses
#  minus IPv4 mapped etc since we probably can't handle them anyway
IPV6_REGEX = (
    r"(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|"  # 1:2:3:4:5:6:7:8
    r"([0-9a-fA-F]{1,4}:){1,7}:|"  # 1::                              1:2:3:4:5:6:7::
    r"([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|"  # 1::8             1:2:3:4:5:6::8  1:2:3:4:5:6::8
    r"([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|"  # 1::7:8           1:2:3:4:5::7:8  1:2:3:4:5::8
    r"([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|"  # 1::6:7:8         1:2:3:4::6:7:8  1:2:3:4::8
    r"([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|"  # 1::5:6:7:8       1:2:3::5:6:7:8  1:2:3::8
    r"([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|"  # 1::4:5:6:7:8     1:2::4:5:6:7:8  1:2::8
    r"[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|"  # 1::3:4:5:6:7:8   1::3:4:5:6:7:8  1::8
    r":((:[0-9a-fA-F]{1,4}){1,7}|:))"
)
HOSTNAME_REGEX = r"^([a-zA-Z0-9-]{1,63})(\.[a-zA-Z-][a-zA-Z0-9-]{0,62})*$"
HOST_REGEX = f"^({IPV4_REGEX}|{IPV6_REGEX}|{HOSTNAME_REGEX})$"
DOMAIN_NAME_REGEX = r"^([a-zA-Z0-9-]{1,63})(\.[a-zA-Z0-9-]{1,63})+$"
host_schema = Field(..., pattern=HOST_REGEX, max_length=253, description="Hostname, FQDN or IP address")
hostname_schema = Field(..., pattern=HOSTNAME_REGEX, max_length=253, description="Hostname or FQDN")
domain_name_schema = Field(default=None, pattern=DOMAIN_NAME_REGEX, max_length=251, description="DNS domain name")
ipv4_schema = Field(..., pattern=f"^{IPV4_REGEX}$", description="IPv4 address")
IPV4_IF_REGEX = f"{IPV4_REGEX}" + r"\/[0-9]{1,2}"
ipv4_if_schema = Field(pattern=f"^{IPV4_IF_REGEX}$", description="IPv4 address in CIDR/prefix notation (0.0.0.0/0)")
ipv6_schema = Field(..., pattern=f"^{IPV6_REGEX}$", description="IPv6 address")
IPV6_IF_REGEX = f"{IPV6_REGEX}" + r"\/[0-9]{1,3}"
ipv6_if_schema = Field(pattern=f"^{IPV6_IF_REGEX}$", description="IPv6 address in CIDR/prefix notation (::/0)")
ipv6_if_schema_optional = Field(
    default=None, pattern=f"^{IPV6_IF_REGEX}$", description="IPv6 address in CIDR/prefix notation (::/0)"
)
ipv4_or_ipv6_if_schema = Field(pattern=f"({IPV4_IF_REGEX}|{IPV6_IF_REGEX})", description="IPv4 or IPv6 prefix")

# VLAN name is alphanumeric max 32 chars on Cisco
# should not start with number according to some Juniper doc
VLAN_NAME_REGEX = r"^[a-zA-Z][a-zA-Z0-9-_]{0,31}$"
vlan_name_schema = Field(
    pattern=VLAN_NAME_REGEX, description="Max 32 alphanumeric chars, " + "beginning with a non-numeric character"
)
vlan_name_schema_optional = Field(
    default=None,
    pattern=VLAN_NAME_REGEX,
    description="Max 32 alphanumeric chars, " + "beginning with a non-numeric character",
)
vlan_id_schema = Field(..., gt=0, lt=4096, description="Numeric 802.1Q VLAN ID, 1-4095")
vlan_id_schema_optional = Field(default=None, gt=0, lt=4096, description="Numeric 802.1Q VLAN ID, 1-4095")
vxlan_vni_schema = Field(..., gt=0, lt=16777215, description="VXLAN Network Identifier")
vrf_id_schema = Field(..., gt=0, lt=65536, description="VRF identifier, integer between 1-65535")
mtu_schema = Field(default=None, ge=68, le=9214, description="MTU (Maximum transmission unit) value between 68-9214")
as_num_schema = Field(
    gt=0, lt=4294967296, description="BGP Autonomous System number, 1-4294967295 (asdot notation not supported)"
)
as_num_schema_optional = Field(
    default=None,
    gt=0,
    lt=4294967296,
    description="BGP Autonomous System number, 1-4294967295 (asdot notation not supported)",
)
IFNAME_REGEX = r"([a-zA-Z0-9\/\.:-])+"
ifname_schema = Field(default=None, pattern=f"^{IFNAME_REGEX}$", description="Interface name")
IFNAME_RANGE_REGEX = r"([a-zA-Z0-9\/\.:\-\[\]])+"
ifname_range_schema = Field(pattern=f"^{IFNAME_RANGE_REGEX}$", description="Interface range pattern or interface name")
IFCLASS_REGEX = r"(custom|downlink|fabric|mirror|port_template_[a-zA-Z0-9_]+)"
ifclass_schema = Field(pattern=f"^{IFCLASS_REGEX}$", description="Interface class: custom, downlink or uplink")
ifdescr_schema = Field(default=None, max_length=64, description="Interface description, 0-64 characters")
tcpudp_port_schema = Field(default=None, ge=0, lt=65536, description="TCP or UDP port number, 0-65535")
ebgp_multihop_schema = Field(default=None, ge=1, le=255, description="Numeric IP TTL, 1-255")
maximum_routes_schema = Field(
    default=None, ge=0, le=4294967294, description="Maximum number of routes to receive from peer"
)
accept_or_reject_schema = Field(..., pattern=r"^(accept|reject)$", description="Value has to be 'accept' or 'reject'")
prefix_size_or_range_schema = Field(pattern=r"^[0-9]{1,3}([-][0-9]{1,3})?$", description="Prefix size or range 0-128")

GROUP_NAME = r"^([a-zA-Z0-9_-]{1,63}\.?)+$"
group_name = Field(..., pattern=GROUP_NAME, max_length=253)
group_priority_schema = Field(
    0, ge=0, le=100, description="Group priority 0-100, default 0, higher value means higher priority"
)
ACCESS_LIST_NAME = r"^([a-zA-Z0-9_-]{1,63}\.?)+$"
access_list_name = Annotated[str, Field(pattern=ACCESS_LIST_NAME, max_length=63)]  # Type


class RemovePrivateASEnum(StrEnum):
    ALL = auto()
    REPLACE = auto()


class VlanOptionEnum(StrEnum):
    NONE = auto()
    TAGGED = auto()
    UNTAGGED = auto()


def validate_ipv4_if(ipv4if: str):
    try:
        assert "/" in ipv4if, "Not a CIDR notation/no netmask"
        addr = IPv4Interface(ipv4if)
        assert 8 <= addr.network.prefixlen <= 32, "Invalid prefix size"
        assert not addr.is_multicast, "Multicast address is invalid"
        if addr.network.prefixlen <= 30:
            assert str(addr.ip) != str(addr.network.network_address), "Invalid interface address"
            assert str(addr.ip) != str(addr.network.broadcast_address), "Invalid interface address"
    except AddressValueError as e:
        raise ValueError("Invalid IPv4 interface: {}".format(e))
    except AssertionError as e:
        raise ValueError("Invalid IPv4 interface: {}".format(e))
    return ipv4if


def vlan_range_check(v: str) -> str:
    if "-" in v:
        start, end = v.split("-")
        assert int(start) < int(end), "Start of range must be less than end of range"
        assert int(start) >= 1 and int(end) <= 4095, "VLAN IDs in range must be between 1-4095"
    else:
        assert 1 <= int(v) <= 4095, "VLAN IDs in range must be between 1-4095"
    return v


def vni_range_required_check(v: str) -> str:
    if "-" in v:
        start, end = v.split("-")
        assert int(start) < int(end), "Start of range must be less than end of range"
        assert int(start) >= 1 and int(end) <= 16777215, "VNI IDs in range must be between 1-16777215"
    else:
        raise ValueError("Range must be specified, ex '10000-99999'")
    return v
