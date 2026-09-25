from enum import StrEnum, auto
from ipaddress import (
    IPv4Address as StdIPv4Address,
)
from ipaddress import (
    IPv4Interface as StdIPv4Interface,
)
from ipaddress import (
    IPv6Address as StdIPv6Address,
)
from ipaddress import (
    IPv6Interface as StdIPv6Interface,
)
from typing import Annotated, Literal

from annotated_types import Ge, Gt, Le, Lt
from pydantic import AfterValidator, Field, PlainSerializer, StringConstraints, TypeAdapter

type BuiltInInterfaceClass = Literal[
    "custom",
    "downlink",
    "fabric",
    "mirror",
]

type PortTemplateInterfaceClass = Annotated[
    str,
    StringConstraints(pattern=r"^port_template_[A-Za-z0-9_]+$"),
]

type InterfaceClass = Annotated[
    BuiltInInterfaceClass | PortTemplateInterfaceClass,
    Field(description="Interface class: custom, downlink, fabric, mirror, or a port template"),
]

type InterfaceDescription = Annotated[
    str, StringConstraints(max_length=64), Field(description="Interface description, 0-64 characters")
]

IFNAME_REGEX = r"([a-zA-Z0-9\/\.:-])+"
type InterfaceName = Annotated[
    str, StringConstraints(pattern=IFNAME_REGEX, max_length=64), Field(description="Interface name, 0-64 characters")
]

IFNAME_RANGE_REGEX = r"([a-zA-Z0-9\/\.:\-\[\]])+"
type InterfaceRange = Annotated[
    str,
    StringConstraints(pattern=IFNAME_RANGE_REGEX, max_length=64),
    Field(description="Interface range, 0-64 characters"),
]

ACCESS_LIST_NAME_REGEX = r"^([a-zA-Z0-9_-]{1,63}\.?)+$"
type AccessListName = Annotated[str, StringConstraints(pattern=ACCESS_LIST_NAME_REGEX, max_length=63)]

HOSTNAME_REGEX = r"^([a-zA-Z0-9-]{1,63})(\.[a-zA-Z-][a-zA-Z0-9-]{0,62})*$"
type HostName = Annotated[str, StringConstraints(pattern=HOSTNAME_REGEX, max_length=253), Field(description="Hostname")]

DOMAIN_NAME_REGEX = r"^([a-zA-Z0-9-]{1,63})(\.[a-zA-Z0-9-]{1,63})+$"
type DomainName = Annotated[
    str, StringConstraints(pattern=DOMAIN_NAME_REGEX, max_length=251), Field(description="DNS domain name")
]

type Host = Annotated[HostName | StdIPv4Address | StdIPv6Address, Field(description="Hostname, FQDN or IP address")]

type AcceptReject = Literal["accept", "reject"]

NET_NAME_REGEX = r"^[a-zA-Z][a-zA-Z0-9-_]{0,31}$"
type NetName = Annotated[
    str,
    StringConstraints(pattern=NET_NAME_REGEX, max_length=32),
    Field(description="Max 32 alphanumeric chars, beginning with a non-numeric character"),
]

type VlanId = Annotated[int, Ge(1), Le(4094), Field(description="Numeric 802.1Q VLAN ID, 1-4094")]

_vlan_id_adapter: TypeAdapter = TypeAdapter(VlanId)


def vlan_range_check(value: str) -> str:
    parts = value.split("-")

    vlan_ids = [_vlan_id_adapter.validate_python(part) for part in parts]

    if len(vlan_ids) == 2 and vlan_ids[0] >= vlan_ids[1]:
        raise ValueError("Start of range must be less than end of range")

    return value


type VlanIdRange = Annotated[
    str,
    Field(description=("A VLAN ID or inclusive VLAN ID range. Valid values are 1-4094 or a range such as '100-200'.")),
    StringConstraints(
        pattern=r"^[1-9]\d{0,3}(-[1-9]\d{0,3})?$",
    ),
    AfterValidator(vlan_range_check),
]

type VxlanNetworkIdentifier = Annotated[int, Gt(0), Lt(16777215), Field(description="VXLAN Network Identifier")]

type VrfId = Annotated[int, Gt(0), Lt(65536), Field(description="VRF identifier, integer between 1-65535")]

type Mtu = Annotated[int, Ge(68), Le(9214), Field(description="MTU (Maximum transmission unit) value between 68-9214")]

type AsNum = Annotated[
    int,
    Gt(0),
    Lt(4294967296),
    Field(description="BGP Autonomous System number, 1-4294967295 (asdot notation not supported)"),
]

type TcpUdpPort = Annotated[int, Ge(0), Lt(65536), Field(description="TCP or UDP port number, 0-65535")]

type EBGPMultihop = Annotated[int, Ge(1), Le(255), Field(description="Numeric IP TTL, 1-255")]

type MaximumRoutes = Annotated[
    int, Ge(0), Le(4294967294), Field(description="Maximum number of routes to receive from peer")
]

GROUP_NAME = r"^([a-zA-Z0-9_-]{1,63}\.?)+$"
type GroupName = Annotated[str, StringConstraints(pattern=GROUP_NAME, max_length=253)]

type GroupPriority = Annotated[
    int, Ge(0), Le(100), Field(description="Group priority 0-100, higher value means higher priority")
]


class RemovePrivateASEnum(StrEnum):
    ALL = auto()
    REPLACE = auto()


class VlanOptionEnum(StrEnum):
    NONE = auto()
    TAGGED = auto()
    UNTAGGED = auto()


def validate_ipv4_interface(value: StdIPv4Interface) -> StdIPv4Interface:
    assert 8 <= value.network.prefixlen <= 32, "Invalid prefix size"
    assert not value.is_multicast, "Multicast address is invalid"

    if value.network.prefixlen <= 30:
        assert value.ip != value.network.network_address, "Invalid interface address"
        assert value.ip != value.network.broadcast_address, "Invalid interface address"

    return value


def validate_ipv6_interface(value: StdIPv6Interface) -> StdIPv6Interface:
    assert 8 <= value.network.prefixlen <= 128, "Invalid prefix size"
    assert not value.is_multicast, "Multicast address is invalid"

    return value


type ValidatedIPv4InterfaceString = Annotated[
    StdIPv4Interface, AfterValidator(validate_ipv4_interface), PlainSerializer(str, return_type=str)
]

type ValidatedIPv6InterfaceString = Annotated[
    StdIPv6Interface, AfterValidator(validate_ipv6_interface), PlainSerializer(str, return_type=str)
]

type IPv4InterfaceString = Annotated[StdIPv4Interface, PlainSerializer(str, return_type=str)]
type IPv6InterfaceString = Annotated[StdIPv6Interface, PlainSerializer(str, return_type=str)]


def vni_range_required_check(v: str) -> str:
    if "-" in v:
        start, end = v.split("-")
        assert int(start) < int(end), "Start of range must be less than end of range"
        assert int(start) >= 1 and int(end) <= 16777215, "VNI IDs in range must be between 1-16777215"
    else:
        raise ValueError("Range must be specified, ex '10000-99999'")
    return v
