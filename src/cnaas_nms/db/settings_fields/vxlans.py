from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from cnaas_nms.db.settings_fields.base_system import f_dhcp_relay
from cnaas_nms.db.settings_fields.shared import (
    ValidatedIPv4InterfaceString,
    ValidatedIPv6InterfaceString,
    Mtu,
    NetName,
    VlanId,
    VlanIdRange,
    VxlanNetworkIdentifier,
    vlan_range_check,
)


class f_vxlan(BaseModel):
    description: str | None = None
    vni: VxlanNetworkIdentifier
    vrf: NetName | None = None
    vlan_id: VlanId
    vlan_name: NetName
    ipv4_gw: ValidatedIPv4InterfaceString | None = None
    ipv4_secondaries: list[ValidatedIPv4InterfaceString] | None = None
    ipv6_gw: ValidatedIPv6InterfaceString | None = None
    dhcp_relays: list[f_dhcp_relay] | None = None
    mtu: Mtu | None = None
    vxlan_host_route: bool = True
    acl_ipv4_in: str | None = None
    acl_ipv4_out: str | None = None
    acl_ipv6_in: str | None = None
    acl_ipv6_out: str | None = None
    cli_append_str: str = ""
    groups: list[str] = Field(default_factory=list)
    devices: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("ipv4_gw", "ipv6_gw", mode="after")
    @classmethod
    def vrf_required_if_ip_gw_set(
        cls, ip_if: ValidatedIPv4InterfaceString | ValidatedIPv6InterfaceString | None, info: ValidationInfo
    ) -> ValidatedIPv4InterfaceString | ValidatedIPv6InterfaceString | None:
        if not ip_if:
            return ip_if

        if ip_if and not info.data.get("vrf"):
            raise ValueError("VRF is required when specifying IP gateway")
        return ip_if


class f_vxlans(BaseModel):
    vxlans: dict[str, f_vxlan] = Field(default_factory=dict)
    vlan_groups: dict[str, list[VlanId]] = Field(
        default_factory=dict,
        description=(
            "Mapping of VLAN group names to sets of VLAN IDs or VLAN ranges. "
            "Use integers for individual VLANs, such as 10, and strings in "
            "'start-end' format for ranges, such as '20-30'."
        ),
        examples=[
            {
                "ACCESS_TRUNK_VLANS": [10, "20-30"],
                "SERVER_VLANS": [100, 200],
            }
        ],
    )

    @field_validator(
        "vlan_groups",
        mode="before",
        json_schema_input_type=dict[str, list[VlanId | VlanIdRange]],
    )
    @classmethod
    def normalize_vlan_groups(
        cls,
        value: Any,
    ) -> dict[str, list[VlanId]]:
        normalized: dict[str, list[VlanId]] = {}

        for group_name, entries in value.items():
            if isinstance(entries, int | str):
                entries = [entries]

            if not isinstance(entries, list | tuple):
                raise ValueError(f"VLAN group {group_name!r} must contain a list, or tuple")

            vlans: list[VlanId] = []

            for entry in entries:
                if isinstance(entry, str) and "-" in entry:
                    # Validate str range
                    vlan_range_check(entry)
                    start, end = map(int, entry.split("-"))

                    vlans.extend(range(start, end + 1))
                elif isinstance(entry, int):
                    vlans.append(int(entry))
                else:
                    raise ValueError(f"Invalid VLAN entry {entry!r} in group {group_name!r}")

            normalized[group_name] = list(set(vlans))

        return normalized
