from pydantic import BaseModel, ValidationInfo, field_validator, model_validator

from cnaas_nms.db.settings_fields.shared import (
    ValidatedIPv4InterfaceString,
    ValidatedIPv6InterfaceString,
    InterfaceClass,
    InterfaceDescription,
    InterfaceRange,
    Mtu,
    NetName,
    VlanId,
    VlanIdRange,
)


class f_interface(BaseModel):
    name: InterfaceRange
    ifclass: InterfaceClass
    redundant_link: bool = True
    config: str | None = None
    description: InterfaceDescription | None = None
    enabled: bool | None = None
    untagged_vlan: VlanId | None = None
    # tagged vlan list can be list of vlans IDs or ranges of VLAN IDs ("1-10")
    tagged_vlan_list: list[VlanId | VlanIdRange | str] | None = None
    tagged_vlan_groups: list[str] | None = None
    aggregate_id: int | None = None
    tags: list[str] | None = None
    vrf: NetName | None = None
    ipv4_address: ValidatedIPv4InterfaceString | None = None
    ipv6_address: ValidatedIPv6InterfaceString | None = None
    mtu: Mtu | None = None
    acl_ipv4_in: str | None = None
    acl_ipv4_out: str | None = None
    acl_ipv6_in: str | None = None
    acl_ipv6_out: str | None = None
    metric: int | None = None
    cli_append_str: str = ""

    @field_validator("ipv4_address", "ipv6_address", mode="after")
    @classmethod
    def vrf_required_if_ip_gw_set(
        cls, ip_if: ValidatedIPv4InterfaceString | ValidatedIPv6InterfaceString | None, info: ValidationInfo
    ) -> ValidatedIPv4InterfaceString | ValidatedIPv6InterfaceString | None:
        if not ip_if:
            return ip_if

        if ip_if and not info.data.get("vrf"):
            raise ValueError("VRF is required when specifying IP address")
        return ip_if

    @model_validator(mode="after")
    def validate_tagged_vlans(self):
        if self.tagged_vlan_list and self.tagged_vlan_groups:
            raise ValueError("tagged_vlan_list and tagged_vlan_groups cannot be set at the same time")
        return self


class f_interfaces(BaseModel):
    interfaces: list[f_interface] = []
