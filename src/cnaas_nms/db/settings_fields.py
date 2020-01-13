from typing import List, Optional, Dict

from pydantic import BaseModel, Schema


# HOSTNAME_REGEX = r'([a-z0-9-]{1,63}\.?)+'
IPV4_REGEX = (r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
              r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)')
# IPv6 regex from https://stackoverflow.com/questions/53497/regular-expression-that-matches-valid-ipv6-addresses
#  minus IPv4 mapped etc since we probably can't handle them anyway
IPV6_REGEX = (
    r'(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|'         # 1:2:3:4:5:6:7:8
    r'([0-9a-fA-F]{1,4}:){1,7}:|'                         # 1::                              1:2:3:4:5:6:7::
    r'([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|'         # 1::8             1:2:3:4:5:6::8  1:2:3:4:5:6::8
    r'([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|'  # 1::7:8           1:2:3:4:5::7:8  1:2:3:4:5::8
    r'([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|'  # 1::6:7:8         1:2:3:4::6:7:8  1:2:3:4::8
    r'([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|'  # 1::5:6:7:8       1:2:3::5:6:7:8  1:2:3::8
    r'([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|'  # 1::4:5:6:7:8     1:2::4:5:6:7:8  1:2::8
    r'[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|'       # 1::3:4:5:6:7:8   1::3:4:5:6:7:8  1::8  
    r':((:[0-9a-fA-F]{1,4}){1,7}|:))'
)
FQDN_REGEX = r'([a-z0-9-]{1,63}\.)([a-z0-9-]{1,63}\.?)+'
HOST_REGEX = f"^({IPV4_REGEX}|{FQDN_REGEX})$"
HOSTNAME_REGEX = r"^([a-z0-9-]{1,63})(\.[a-z0-9-]{1,63})*$"
host_schema = Schema(..., regex=HOST_REGEX, max_length=253)
hostname_schema = Schema(..., regex=HOSTNAME_REGEX, max_length=253)
ipv4_schema = Schema(..., regex=f"^{IPV4_REGEX}$")
IPV4_IF_REGEX = f"{IPV4_REGEX}" + r"\/[0-9]{1,2}"
ipv4_if_schema = Schema(..., regex=f"^{IPV4_IF_REGEX}$")
ipv6_schema = Schema(..., regex=f"^{IPV6_REGEX}$")
IPV6_IF_REGEX = f"{IPV6_REGEX}" + r"\/[0-9]{1,3}"
ipv6_if_schema = Schema(..., regex=f"^{IPV6_IF_REGEX}$")

# VLAN name is alphanumeric max 32 chars on Cisco
# should not start with number according to some Juniper doc
VLAN_NAME_REGEX = r'^[a-zA-Z][a-zA-Z0-9-_]{0,31}$'
vlan_name_schema = Schema(..., regex=VLAN_NAME_REGEX,
                          description="Max 32 alphanumeric chars, " +
                                      "beginning with a non-numeric character")
vlan_id_schema = Schema(..., gt=0, lt=4096, description="Numeric 802.1Q VLAN ID, 1-4095")
vxlan_vni_schema = Schema(..., gt=0, lt=16777215, description="VXLAN Network Identifier")
vrf_id_schema = Schema(..., gt=0, lt=65536, description="VRF identifier, integer between 1-65535")

GROUP_NAME = r'^([a-zA-Z0-9_]{1,63}\.?)+$'
group_name = Schema(..., regex=GROUP_NAME, max_length=253)


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


class f_syslog_server(BaseModel):
    host: str = host_schema


class f_snmp_server(BaseModel):
    host: str = host_schema


class f_evpn_spine(BaseModel):
    hostname: str = hostname_schema


class f_interface(BaseModel):
    name: str
    ifclass: str
    config: Optional[str] = None


class f_vrf(BaseModel):
    name: str = None
    vrf_id: int = vrf_id_schema
    groups: List[str] = []


class f_ipv4_static_route(BaseModel):
    destination: str = ipv4_if_schema
    nexthop: str = ipv4_schema
    interface: Optional[str] = None
    name: str = "undefined"
    cli_append_str: str = ""


class f_ipv6_static_route(BaseModel):
    destination: str = ipv6_if_schema
    nexthop: str = ipv6_schema
    interface: Optional[str] = None
    name: str = "undefined"
    cli_append_str: str = ""


class f_extroute_static_vrf(BaseModel):
    name: str
    ipv4: List[f_ipv4_static_route]
    ipv6: List[f_ipv6_static_route]


class f_extroute_static(BaseModel):
    vrfs: List[f_extroute_static_vrf]


class f_extroute_ospfv3_vrf(BaseModel):
    name: str
    ipv4_redist_routefilter: Optional[str] = None
    ipv6_redist_routefilter: Optional[str] = None
    cli_append_str: str = ""


class f_extroute_ospfv3(BaseModel):
    vrfs: List[f_extroute_ospfv3_vrf]


class f_vxlan(BaseModel):
    description: str = None
    vni: int = vxlan_vni_schema
    vrf: str = vlan_name_schema
    vlan_id: int = vlan_id_schema
    vlan_name: str = vlan_name_schema
    ipv4_gw: str = ipv4_if_schema
    groups: List[str] = []
    devices: List[str] = []


class f_underlay(BaseModel):
    infra_lo_net: str = ipv4_if_schema
    infra_link_net: str = ipv4_if_schema
    mgmt_lo_net: str = ipv4_if_schema


class f_root(BaseModel):
    ntp_servers: List[f_ntp_server] = []
    radius_servers: List[f_radius_server] = []
    syslog_servers: List[f_syslog_server] = []
    snmp_servers: List[f_snmp_server] = []
    interfaces: List[f_interface] = []
    vrfs: List[f_vrf] = []
    vxlans: Dict[str, f_vxlan] = {}
    underlay: f_underlay = None
    evpn_spines: List[f_evpn_spine] = []
    extroute_static: Optional[f_extroute_static]
    extroute_ospfv3: Optional[f_extroute_ospfv3]
    cli_prepend_str: str = ""
    cli_append_str: str = ""


class f_group_item(BaseModel):
    name: str = group_name
    regex: str = ''


class f_group(BaseModel):
    group: Optional[f_group_item]


class f_groups(BaseModel):
    groups: Optional[List[f_group]]
