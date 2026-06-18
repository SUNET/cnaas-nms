from typing import Annotated, Dict, List, Optional

from pydantic import BaseModel, ValidationInfo, field_validator
from pydantic.functional_validators import AfterValidator

from cnaas_nms.db.settings_fields.shared import (
    VlanOptionEnum,
    access_list_name,
    domain_name_schema,
    host_schema,
    tcpudp_port_schema,
    vlan_id_schema,
    vlan_id_schema_optional,
)


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


class f_internal_vlans(BaseModel):
    vlan_id_low: int = vlan_id_schema
    vlan_id_high: int = vlan_id_schema
    allocation_order: str = "ascending"

    @field_validator("vlan_id_high")
    @classmethod
    def vlan_id_high_greater_than_low(cls, v: int, info: ValidationInfo):
        if v:
            if info.data["vlan_id_low"] >= v:
                raise ValueError("vlan_id_high must be greater than vlan_id_low")
        return v


class f_interface_tag(BaseModel):
    description: str = ""
    groups: Optional[List[str]] = None


class f_port_template(BaseModel):
    description: str = ""
    vlan_config: VlanOptionEnum = VlanOptionEnum.TAGGED
    groups: Optional[List[str]] = None


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


class f_base_system(BaseModel):
    ntp_servers: List[f_ntp_server] = []
    radius_servers: List[f_radius_server] = []
    syslog_servers: List[f_syslog_server] = []
    snmp_servers: List[f_snmp_server] = []
    dns_servers: List[f_dns_server] = []
    flow_collectors: List[f_flow_collector] = []
    dhcp_relays: Optional[List[f_dhcp_relay]] = None
    internal_vlans: Optional[f_internal_vlans] = None
    dot1x_fail_vlan: Optional[int] = vlan_id_schema_optional
    cli_prepend_str: str = ""
    cli_append_str: str = ""
    organization_name: str = ""
    domain_name: Optional[str] = domain_name_schema
    users: List[f_user] = []
    dot1x_multi_host: bool = False
    poe_reboot_maintain: bool = False
    interface_tag_options: Dict[str, f_interface_tag] = {}
    port_template_options: Dict[str, f_port_template] = {}
    vxlan_vni_range: Optional[Annotated[str, AfterValidator(vni_range_required_check)]] = None
    arista_models_32bit: Optional[List[str]] = None
    upgrade_post_waittime: Dict[str, int] = {"default": 600}
    system_access_lists: List[access_list_name] = []
    # This is defined both in f_base_system and f_routing
    external_routing_policies: List[str] = []
