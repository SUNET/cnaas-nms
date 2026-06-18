from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator
from pydantic.functional_validators import AfterValidator

from cnaas_nms.db.settings_fields.shared import (
    ifclass_schema,
    ifdescr_schema,
    ifname_range_schema,
    ipv6_if_schema_optional,
    mtu_schema,
    validate_ipv4_if,
    vlan_id_schema_optional,
    vlan_name_schema_optional,
    vlan_range_check,
)


class f_interface(BaseModel):
    name: str = ifname_range_schema
    ifclass: str = ifclass_schema
    redundant_link: bool = True
    config: Optional[str] = None
    description: Optional[str] = ifdescr_schema
    enabled: Optional[bool] = None
    untagged_vlan: Optional[int] = vlan_id_schema_optional
    # tagged vlan list can be list of vlans IDs or ranges of VLAN IDs ("1-10")
    tagged_vlan_list: Optional[
        List[Annotated[int, Field(ge=1, le=4095)] | Annotated[str, AfterValidator(vlan_range_check)]]
    ] = None
    aggregate_id: Optional[int] = None
    tags: Optional[List[str]] = None
    vrf: Optional[str] = vlan_name_schema_optional
    ipv4_address: Optional[str] = None
    ipv6_address: Optional[str] = ipv6_if_schema_optional
    mtu: Optional[int] = mtu_schema
    acl_ipv4_in: Optional[str] = None
    acl_ipv4_out: Optional[str] = None
    acl_ipv6_in: Optional[str] = None
    acl_ipv6_out: Optional[str] = None
    metric: Optional[int] = None
    cli_append_str: str = ""

    @field_validator("ipv4_address")
    @classmethod
    def vrf_required_if_ipv4_address_set(cls, v: str, info: ValidationInfo):
        if v:
            validate_ipv4_if(v)
            if "vrf" not in info.data or not info.data["vrf"]:
                raise ValueError("VRF is required when specifying ipv4_gw")
        return v


class f_interfaces(BaseModel):
    interfaces: List[f_interface] = []
