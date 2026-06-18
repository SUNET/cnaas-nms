from typing import Annotated, Dict, List, Optional

from pydantic import BaseModel, ValidationInfo, field_validator
from pydantic.functional_validators import AfterValidator

from cnaas_nms.db.settings_fields.base_system import f_dhcp_relay
from cnaas_nms.db.settings_fields.shared import (
    ipv6_if_schema_optional,
    mtu_schema,
    validate_ipv4_if,
    vlan_id_schema,
    vlan_name_schema,
    vlan_name_schema_optional,
    vxlan_vni_schema,
)


class f_vxlan(BaseModel):
    description: Optional[str] = None
    vni: int = vxlan_vni_schema
    vrf: Optional[str] = vlan_name_schema_optional
    vlan_id: int = vlan_id_schema
    vlan_name: str = vlan_name_schema
    ipv4_gw: Optional[str] = None
    ipv4_secondaries: Optional[List[Annotated[str, AfterValidator(validate_ipv4_if)]]] = None
    ipv6_gw: Optional[str] = ipv6_if_schema_optional
    dhcp_relays: Optional[List[f_dhcp_relay]] = None
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

    @field_validator("ipv4_gw")
    @classmethod
    def vrf_required_if_ipv4_gw_set(cls, v: str, info: ValidationInfo):
        if v:
            validate_ipv4_if(v)
            if "vrf" not in info.data or not info.data["vrf"]:
                raise ValueError("VRF is required when specifying ipv4_gw")
        return v

    @field_validator("ipv6_gw")
    @classmethod
    def vrf_required_if_ipv6_gw_set(cls, v: str, info: ValidationInfo):
        if v:
            if "vrf" not in info.data or not info.data["vrf"]:
                raise ValueError("VRF is required when specifying ipv6_gw")
        return v


class f_vxlans(BaseModel):
    vxlans: Dict[str, f_vxlan] = {}
