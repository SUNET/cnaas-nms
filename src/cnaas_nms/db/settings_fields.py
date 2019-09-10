from typing import List, Optional

from pydantic import BaseModel, Schema


# HOSTNAME_REGEX = r'([a-z0-9-]{1,63}\.?)+'
IPV4_REGEX = (r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
              r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)')
FQDN_REGEX = r'([a-z0-9-]{1,63}\.)([a-z0-9-]{1,63}\.?)+'
HOST_REGEX = f"^({IPV4_REGEX}|{FQDN_REGEX})$"
host_schema = Schema(..., regex=HOST_REGEX, max_length=253)
IPV4_IF_REGEX = f"{IPV4_REGEX}" + r"\/[0-9]{1,2}"
ipv4_if_schema = Schema(..., regex=IPV4_IF_REGEX)

# VLAN name is alphanumeric max 32 chars on Cisco
# should not start with number according to some Juniper doc
VLAN_NAME_REGEX = r'^[a-zA-Z][a-zA-Z0-9-_]{0,31}$'
vlan_name_schema = Schema(..., regex=VLAN_NAME_REGEX)
vlan_id_schema = Schema(..., gt=0, lt=4096)


GROUP_NAME = r'^([a-zA-Z0-9_]{1,63}\.?)+$'
group_name = Schema(..., regex=GROUP_NAME, max_length=253)


class f_ntp_server(BaseModel):
    host: str = host_schema


class f_radius_server(BaseModel):
    host: str = host_schema


class f_syslog_server(BaseModel):
    host: str = host_schema


class f_interface(BaseModel):
    name: str = None
    ifclass: str = None
    config: Optional[str] = None


class f_vrf(BaseModel):
    name: str = None
    rd: str = None
    groups: List[str] = []


class f_vxlan(BaseModel):
    name: str = None
    vlan_id: int = vlan_id_schema
    vlan_name: str = vlan_name_schema
    ipv4_gw: str = ipv4_if_schema
    groups: List[str] = []
    devices: List[str] = []


class f_root(BaseModel):
    ntp_servers: List[f_ntp_server] = []
    radius_servers: List[f_radius_server] = []
    syslog_servers: List[f_syslog_server] = []
    interfaces: List[f_interface] = []
    vrfs: List[f_vrf] = []
    vxlans: List[f_vxlan] = []


class f_group_item(BaseModel):
    name: str = group_name
    regex: str = ''


class f_group(BaseModel):
    group: Optional[f_group_item]


class f_groups(BaseModel):
    groups: Optional[List[f_group]]
