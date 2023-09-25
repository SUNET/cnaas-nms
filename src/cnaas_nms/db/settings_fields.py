from ipaddress import AddressValueError, IPv4Interface
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, conint, validator

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
FQDN_REGEX = r"([a-zA-Z0-9-]{1,63}\.)([a-z-][a-z0-9-]{1,62}\.?)+"
HOST_REGEX = f"^({IPV4_REGEX}|{IPV6_REGEX}|{FQDN_REGEX})$"
HOSTNAME_REGEX = r"^([a-zA-Z0-9-]{1,63})(\.[a-z0-9-]{1,63})*$"
DOMAIN_NAME_REGEX = r"^([a-zA-Z0-9-]{1,63})(\.[a-z0-9-]{1,63})+$"
host_schema = Field(..., regex=HOST_REGEX, max_length=253, description="Hostname, FQDN or IP address")
hostname_schema = Field(..., regex=HOSTNAME_REGEX, max_length=253, description="Hostname or FQDN")
domain_name_schema = Field(None, regex=DOMAIN_NAME_REGEX, max_length=251, description="DNS domain name")
ipv4_schema = Field(..., regex=f"^{IPV4_REGEX}$", description="IPv4 address")
IPV4_IF_REGEX = f"{IPV4_REGEX}" + r"\/[0-9]{1,2}"
ipv4_if_schema = Field(None, regex=f"^{IPV4_IF_REGEX}$", description="IPv4 address in CIDR/prefix notation (0.0.0.0/0)")
ipv6_schema = Field(..., regex=f"^{IPV6_REGEX}$", description="IPv6 address")
IPV6_IF_REGEX = f"{IPV6_REGEX}" + r"\/[0-9]{1,3}"
ipv6_if_schema = Field(None, regex=f"^{IPV6_IF_REGEX}$", description="IPv6 address in CIDR/prefix notation (::/0)")
ipv4_or_ipv6_if_schema = Field(None, regex=f"({IPV4_IF_REGEX}|{IPV6_IF_REGEX})", description="IPv4 or IPv6 prefix")

# VLAN name is alphanumeric max 32 chars on Cisco
# should not start with number according to some Juniper doc
VLAN_NAME_REGEX = r"^[a-zA-Z][a-zA-Z0-9-_]{0,31}$"
vlan_name_schema = Field(
    None, regex=VLAN_NAME_REGEX, description="Max 32 alphanumeric chars, " + "beginning with a non-numeric character"
)
vlan_id_schema = Field(..., gt=0, lt=4096, description="Numeric 802.1Q VLAN ID, 1-4095")
vlan_id_schema_optional = Field(None, gt=0, lt=4096, description="Numeric 802.1Q VLAN ID, 1-4095")
vxlan_vni_schema = Field(..., gt=0, lt=16777215, description="VXLAN Network Identifier")
vrf_id_schema = Field(..., gt=0, lt=65536, description="VRF identifier, integer between 1-65535")
mtu_schema = Field(None, ge=68, le=9214, description="MTU (Maximum transmission unit) value between 68-9214")
as_num_schema = Field(None, description="BGP Autonomous System number, 1-4294967295 (asdot notation not supported)")
as_num_type = conint(strict=True, gt=0, lt=4294967296)
IFNAME_REGEX = r"([a-zA-Z0-9\/\.:-])+"
ifname_schema = Field(None, regex=f"^{IFNAME_REGEX}$", description="Interface name")
IFNAME_RANGE_REGEX = r"([a-zA-Z0-9\/\.:\-\[\]])+"
ifname_range_schema = Field(
    None, regex=f"^{IFNAME_RANGE_REGEX}$", description="Interface range pattern or interface name"
)
IFCLASS_REGEX = r"(custom|downlink|fabric|port_template_[a-zA-Z0-9_]+)"
ifclass_schema = Field(None, regex=f"^{IFCLASS_REGEX}$", description="Interface class: custom, downlink or uplink")
ifdescr_schema = Field(None, max_length=64, description="Interface description, 0-64 characters")
tcpudp_port_schema = Field(None, ge=0, lt=65536, description="TCP or UDP port number, 0-65535")
ebgp_multihop_schema = Field(None, ge=1, le=255, description="Numeric IP TTL, 1-255")
maximum_routes_schema = Field(None, ge=0, le=4294967294, description="Maximum number of routes to receive from peer")
accept_or_reject_schema = Field(..., regex=r"^(accept|reject)$", description="Value has to be 'accept' or 'reject'")
prefix_size_or_range_schema = Field(
    None, regex=r"^[0-9]{1,3}([-][0-9]{1,3})?$", description="Prefix size or range 0-128"
)

GROUP_NAME = r"^([a-zA-Z0-9_-]{1,63}\.?)+$"
group_name = Field(..., regex=GROUP_NAME, max_length=253)
group_priority_schema = Field(
    0, ge=0, le=100, description="Group priority 0-100, default 0, higher value means higher priority"
)


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


# Note: If specifying a list of a BaseModel derived class anywhere else except
# f_root you will get validation errors, and the errors does not refer to
# settings from the top level dict but instead use the first level after f_root
# as their top level. This also makes error messages quite useless.
# I don't have a solution for this at the moment, so just put list of classes
# directly under f_root.


class f_ntp_server(BaseModel):
    host: str = host_schema


class f_radius_server(BaseModel):
    host: str = host_schema
    port: Optional[int] = tcpudp_port_schema


class f_syslog_server(BaseModel):
    host: str = host_schema
    port: Optional[int] = tcpudp_port_schema


class f_flow_collector(BaseModel):
    host: str = host_schema
    port: Optional[int] = tcpudp_port_schema


class f_snmp_server(BaseModel):
    host: str = host_schema


class f_dns_server(BaseModel):
    host: str = host_schema


class f_dhcp_relay(BaseModel):
    host: str = host_schema


class f_evpn_peer(BaseModel):
    hostname: str = hostname_schema


class f_interface(BaseModel):
    name: str = ifname_range_schema
    ifclass: str = ifclass_schema
    redundant_link: bool = True
    config: Optional[str] = None
    description: Optional[str] = ifdescr_schema
    enabled: Optional[bool] = None
    untagged_vlan: Optional[int] = vlan_id_schema_optional
    tagged_vlan_list: Optional[List[int]] = None
    aggregate_id: Optional[int] = None
    tags: Optional[List[str]] = None
    vrf: Optional[str] = vlan_name_schema
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = ipv6_if_schema
    mtu: Optional[int] = mtu_schema
    acl_ipv4_in: Optional[str] = None
    acl_ipv4_out: Optional[str] = None
    acl_ipv6_in: Optional[str] = None
    acl_ipv6_out: Optional[str] = None
    cli_append_str: str = ""

    @validator("ipv4_address")
    def vrf_required_if_ipv4_address_set(cls, v, values, **kwargs):
        if v:
            validate_ipv4_if(v)
            if "vrf" not in values or not values["vrf"]:
                raise ValueError("VRF is required when specifying ipv4_gw")
        return v

    @validator("tagged_vlan_list", each_item=True)
    def check_valid_vlan_ids(cls, v):
        assert 0 < v < 4096
        return v


class f_vrf(BaseModel):
    name: str = None
    vrf_id: int = vrf_id_schema
    import_route_targets: List[str] = []
    export_route_targets: List[str] = []
    import_policy: Optional[str] = None
    export_policy: Optional[str] = None
    groups: List[str] = []


class f_ipv4_static_route(BaseModel):
    destination: str = ipv4_if_schema
    nexthop: str = ipv4_schema
    interface: Optional[str] = ifname_schema
    name: str = "undefined"
    cli_append_str: str = ""


class f_ipv6_static_route(BaseModel):
    destination: str = ipv6_if_schema
    nexthop: str = ipv6_schema
    interface: Optional[str] = ifname_schema
    name: str = "undefined"
    cli_append_str: str = ""


class f_extroute_static_vrf(BaseModel):
    name: str
    ipv4: Optional[List[f_ipv4_static_route]]
    ipv6: Optional[List[f_ipv6_static_route]]


class f_extroute_static(BaseModel):
    vrfs: List[f_extroute_static_vrf]


class f_extroute_ospfv3_vrf(BaseModel):
    name: str
    ipv4_redist_routefilter: Optional[str] = None
    ipv6_redist_routefilter: Optional[str] = None
    cli_append_str: str = ""


class f_extroute_ospfv3(BaseModel):
    vrfs: List[f_extroute_ospfv3_vrf]


class f_extroute_bgp_neighbor_v4(BaseModel):
    peer_ipv4: str = ipv4_schema
    peer_as: as_num_type = as_num_schema
    route_map_in: str = vlan_name_schema
    route_map_out: str = vlan_name_schema
    description: str = "undefined"
    bfd: Optional[bool] = None
    graceful_restart: Optional[bool] = None
    next_hop_self: Optional[bool] = None
    update_source: Optional[str] = ifname_schema
    ebgp_multihop: Optional[int] = ebgp_multihop_schema
    maximum_routes: Optional[int] = maximum_routes_schema
    auth_type: Optional[str] = None
    auth_string: Optional[str] = None
    cli_append_str: str = ""


class f_extroute_bgp_neighbor_v6(BaseModel):
    peer_ipv6: str = ipv6_schema
    peer_as: as_num_type = as_num_schema
    route_map_in: str = vlan_name_schema
    route_map_out: str = vlan_name_schema
    description: str = "undefined"
    bfd: Optional[bool] = None
    graceful_restart: Optional[bool] = None
    next_hop_self: Optional[bool] = None
    update_source: Optional[str] = ifname_schema
    ebgp_multihop: Optional[int] = ebgp_multihop_schema
    maximum_routes: Optional[int] = maximum_routes_schema
    auth_type: Optional[str] = None
    auth_string: Optional[str] = None
    cli_append_str: str = ""


class f_extroute_bgp_vrf(BaseModel):
    name: str
    local_as: as_num_type = as_num_schema
    neighbor_v4: List[f_extroute_bgp_neighbor_v4] = []
    neighbor_v6: List[f_extroute_bgp_neighbor_v6] = []
    cli_append_str: str = ""


class f_extroute_bgp(BaseModel):
    vrfs: List[f_extroute_bgp_vrf] = []


class f_internal_vlans(BaseModel):
    vlan_id_low: int = vlan_id_schema
    vlan_id_high: int = vlan_id_schema
    allocation_order: str = "ascending"

    @validator("vlan_id_high")
    def vlan_id_high_greater_than_low(cls, v, values, **kwargs):
        if v:
            if values["vlan_id_low"] >= v:
                raise ValueError("vlan_id_high must be greater than vlan_id_low")
        return v


class f_vxlan(BaseModel):
    description: str = None
    vni: int = vxlan_vni_schema
    vrf: Optional[str] = vlan_name_schema
    vlan_id: int = vlan_id_schema
    vlan_name: str = vlan_name_schema
    ipv4_gw: Optional[str] = None
    ipv4_secondaries: Optional[List[str]]
    ipv6_gw: Optional[str] = ipv6_if_schema
    dhcp_relays: Optional[List[f_dhcp_relay]]
    mtu: Optional[int] = mtu_schema
    vxlan_host_route: bool = True
    acl_ipv4_in: Optional[str] = None
    acl_ipv4_out: Optional[str] = None
    acl_ipv6_in: Optional[str] = None
    acl_ipv6_out: Optional[str] = None
    cli_append_str: str = ""
    groups: List[str] = []
    devices: List[str] = []
    tags: List[str] = []

    @validator("ipv4_secondaries", each_item=True)
    def ipv4_secondaries_regex(cls, v):
        validate_ipv4_if(v)
        return v

    @validator("ipv4_gw")
    def vrf_required_if_ipv4_gw_set(cls, v, values, **kwargs):
        if v:
            validate_ipv4_if(v)
            if "vrf" not in values or not values["vrf"]:
                raise ValueError("VRF is required when specifying ipv4_gw")
        return v

    @validator("ipv6_gw")
    def vrf_required_if_ipv6_gw_set(cls, v, values, **kwargs):
        if v:
            if "vrf" not in values or not values["vrf"]:
                raise ValueError("VRF is required when specifying ipv6_gw")
        return v


class f_underlay(BaseModel):
    infra_lo_net: str = ipv4_if_schema
    infra_link_net: str = ipv4_if_schema
    mgmt_lo_net: str = ipv4_if_schema
    bgp_asn: Optional[as_num_type] = as_num_schema


class f_user(BaseModel):
    username: str
    ssh_key: Optional[str] = None
    uid: Optional[int] = None
    password_hash_arista: Optional[str] = None
    password_hash_cisco: Optional[str] = None
    password_hash_juniper: Optional[str] = None
    permission_arista: Optional[str] = None
    permission_cisco: Optional[str] = None
    permission_juniper: Optional[str] = None
    groups: List[str] = []


class f_prefixset_item(BaseModel):
    prefix: str = ipv4_or_ipv6_if_schema
    masklength_range: Optional[str] = prefix_size_or_range_schema


class f_prefixset(BaseModel):
    mode: str = "ipv4"
    prefixes: List[f_prefixset_item]


class f_rpolicy_condition(BaseModel):
    match_type: str
    match_target: str


class f_rpolicy_statement(BaseModel):
    action: str = accept_or_reject_schema
    conditions: List[f_rpolicy_condition]


class f_routingpolicy(BaseModel):
    statements: List[f_rpolicy_statement]


class f_root(BaseModel):
    ntp_servers: List[f_ntp_server] = []
    radius_servers: List[f_radius_server] = []
    syslog_servers: List[f_syslog_server] = []
    snmp_servers: List[f_snmp_server] = []
    dns_servers: List[f_dns_server] = []
    flow_collectors: List[f_flow_collector] = []
    dhcp_relays: Optional[List[f_dhcp_relay]]
    interfaces: List[f_interface] = []
    vrfs: List[f_vrf] = []
    vxlans: Dict[str, f_vxlan] = {}
    underlay: f_underlay = None
    evpn_peers: List[f_evpn_peer] = []
    extroute_static: Optional[f_extroute_static]
    extroute_ospfv3: Optional[f_extroute_ospfv3]
    extroute_bgp: Optional[f_extroute_bgp]
    internal_vlans: Optional[f_internal_vlans]
    dot1x_fail_vlan: Optional[int] = vlan_id_schema_optional
    cli_prepend_str: str = ""
    cli_append_str: str = ""
    organization_name: str = ""
    domain_name: Optional[str] = domain_name_schema
    users: List[f_user] = []
    dot1x_multi_host: bool = False
    poe_reboot_maintain: bool = False
    prefix_sets: Dict[str, f_prefixset] = {}
    routing_policies: Dict[str, f_routingpolicy] = {}


class f_group_item(BaseModel):
    name: str = group_name
    regex: str = ""
    group_priority: int = group_priority_schema

    @validator("group_priority")
    def reserved_priority(cls, v, values, **kwargs):
        if v and v == 1 and values["name"] != "DEFAULT":
            raise ValueError("group_priority 1 is reserved for built-in group DEFAULT")
        return v


class f_group(BaseModel):
    group: Optional[f_group_item]


class f_groups(BaseModel):
    groups: Optional[List[f_group]]
