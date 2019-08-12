from typing import List, Optional

from pydantic import BaseModel, Schema


IPV4_REGEX = (r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
              r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
HOSTNAME_REGEX = r'^([a-z0-9-]{1,63}\.?)+$'
FQDN_REGEX = r'^([a-z0-9-]{1,63}\.)([a-z0-9-]{1,63}\.?)+$'
HOST_REGEX = f"({IPV4_REGEX}|{FQDN_REGEX})"
host_schema = Schema(..., regex=HOST_REGEX, max_length=253)

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
    group: str = None


class f_root(BaseModel):
    ntp_servers: Optional[List[f_ntp_server]]
    radius_servers: Optional[List[f_radius_server]]
    syslog_servers: Optional[List[f_syslog_server]]
    interfaces: Optional[List[f_interface]]
    vrfs: Optional[List[f_vrf]]


class f_group_item(BaseModel):
    name: str = group_name
    regex: str = ''


class f_group(BaseModel):
    group: Optional[f_group_item]


class f_groups(BaseModel):
    groups: Optional[List[f_group]]
