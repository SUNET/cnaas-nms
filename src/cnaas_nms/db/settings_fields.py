from typing import List, Optional

from pydantic import BaseModel, Schema


IPV4_REGEX = (r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
              r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
HOSTNAME_REGEX = r'^([a-z0-9-]{1,63}\.?)+$'
HOST_REGEX = f"({IPV4_REGEX}|{HOSTNAME_REGEX})"
host_schema = Schema(..., regex=HOST_REGEX, max_length=253)


class f_ntp_server(BaseModel):
    host: str = host_schema


class f_root(BaseModel):
    ntp_servers: List[f_ntp_server]
