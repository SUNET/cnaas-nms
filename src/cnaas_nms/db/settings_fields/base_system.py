from typing import Annotated

from pydantic import BaseModel, ValidationInfo, field_validator
from pydantic.functional_validators import AfterValidator

from cnaas_nms.db.settings_fields.shared import (
    AccessListName,
    DomainName,
    Host,
    TcpUdpPort,
    VlanId,
    VlanOptionEnum,
    vni_range_required_check,
)


class f_ntp_server(BaseModel):
    host: Host


class f_radius_server(BaseModel):
    host: Host
    port: TcpUdpPort | None = None


class f_syslog_server(BaseModel):
    host: Host
    port: TcpUdpPort | None = None


class f_flow_collector(BaseModel):
    host: Host
    port: TcpUdpPort | None = None


class f_snmp_server(BaseModel):
    host: Host


class f_dns_server(BaseModel):
    host: Host


class f_dhcp_relay(BaseModel):
    host: Host


class f_internal_vlans(BaseModel):
    vlan_id_low: VlanId
    vlan_id_high: VlanId
    allocation_order: str = "ascending"

    @field_validator("vlan_id_high")
    @classmethod
    def vlan_id_high_greater_than_low(cls, v: int, info: ValidationInfo):
        if v and info.data["vlan_id_low"] >= v:
            raise ValueError("vlan_id_high must be greater than vlan_id_low")
        return v


class f_interface_tag(BaseModel):
    description: str = ""
    groups: list[str] | None = None


class f_port_template(BaseModel):
    description: str = ""
    vlan_config: VlanOptionEnum = VlanOptionEnum.TAGGED
    groups: list[str] | None = None


class f_user(BaseModel):
    username: str
    ssh_key: str | None = None
    uid: int | None = None
    password_hash_arista: str | None = None
    password_hash_cisco: str | None = None
    password_hash_juniper: str | None = None
    permission_arista: str | None = None
    permission_cisco: str | None = None
    permission_juniper: str | None = None
    groups: list[str] = []


class f_base_system(BaseModel):
    ntp_servers: list[f_ntp_server] = []
    radius_servers: list[f_radius_server] = []
    syslog_servers: list[f_syslog_server] = []
    snmp_servers: list[f_snmp_server] = []
    dns_servers: list[f_dns_server] = []
    flow_collectors: list[f_flow_collector] = []
    dhcp_relays: list[f_dhcp_relay] | None = None
    internal_vlans: f_internal_vlans | None = None
    banner_login: str | None = None
    banner_motd: str | None = None
    dot1x_fail_vlan: VlanId | None = None
    cli_prepend_str: str = ""
    cli_append_str: str = ""
    organization_name: str = ""
    domain_name: DomainName | None = None
    users: list[f_user] = []
    dot1x_multi_host: bool = False
    poe_reboot_maintain: bool = False
    interface_tag_options: dict[str, f_interface_tag] = {}
    port_template_options: dict[str, f_port_template] = {}
    vxlan_vni_range: Annotated[str, AfterValidator(vni_range_required_check)] | None = None
    arista_models_32bit: list[str] | None = None
    arista_models_arm: list[str] | None = None
    upgrade_post_waittime: dict[str, int] = {"default": 600}
    system_access_lists: list[AccessListName] = []
    # This is defined both in f_base_system and f_routing
    external_routing_policies: list[str] = []
