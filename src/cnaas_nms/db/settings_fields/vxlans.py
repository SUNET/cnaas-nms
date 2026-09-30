from typing import Annotated, Any, Self

from annotated_types import Ge, Le
from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from cnaas_nms.db.settings_fields.base_system import f_dhcp_relay
from cnaas_nms.db.settings_fields.shared import (
    Mtu,
    NetName,
    ValidatedIPv4InterfaceString,
    ValidatedIPv6InterfaceString,
    VlanId,
    VlanIdRange,
    VxlanNetworkIdentifier,
    vlan_range_check,
)
from cnaas_nms.tools.log import get_logger


class f_vxlan_igmp_snooping_querier(BaseModel):
    enabled: bool = True
    query_interval: (
        Annotated[
            int,
            Ge(5),
            Le(3600),
            Field(description="IGMP snooping querier query interval in seconds, leave empty to use device defaults."),
        ]
        | None
    ) = None
    version: (
        Annotated[
            int,
            Ge(1),
            Le(3),
            Field(
                description="IGMP snooping querier version, must be between 1 and 3, leave empty to use device defaults."
            ),
        ]
        | None
    ) = None


class f_vxlan_igmp_snooping(BaseModel):
    enabled: bool = True
    querier: f_vxlan_igmp_snooping_querier | None = None

    @model_validator(mode="after")
    def validate_igmp_snooping_querier(self: Self) -> Self:
        if self.querier and not self.enabled:
            raise ValueError("IGMP snooping querier cannot be set if IGMP snooping is disabled")
        if not self.enabled and self.querier and self.querier.enabled:
            raise ValueError("IGMP snooping must be enabled if querier is enabled")
        return self


class f_vxlan(BaseModel):
    description: str | None = None
    enabled: Annotated[bool, Field(description="Whether the VLAN interface is enabled.")] = True
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
    igmp_snooping: f_vxlan_igmp_snooping = Field(default_factory=f_vxlan_igmp_snooping)
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

    @model_validator(mode="after")
    def log_unused_l2l3_options(self: Self) -> Self:
        """Some options are not intended to be used in L2 vs L3 mode."""
        logger = get_logger()
        is_l2 = not self.ipv4_gw and not self.ipv6_gw
        is_l3 = not is_l2

        # In L3 mode IGMP snooping querier should not be set.
        # It is meant for L2 multicast scenarios.
        # Read more about it here:
        # Arista: https://www.arista.com/en/support/toi/eos-4-25-1f/14669-layer-2-multicast-evpn
        # Cisco Nexus: https://www.cisco.com/c/en/us/td/docs/dcn/nx-os/nexus9000/106x/configuration/vxlan/cisco-nexus-9000-series-nx-os-vxlan-configuration-guide-release-106x/optimized-layer-2-overlay-multicast.html#_4cc34282-e9de-4e52-8c41-a9821503db64
        # Juniper: https://www.juniper.net/documentation/us/en/software/junos/evpn/topics/example/evpn-vxlan-igmp-snooping-configuring-qfx-series.html
        # The querier address will be Loopback0 in the EVPN underlay
        if (
            is_l3
            and self.igmp_snooping
            and self.igmp_snooping.enabled
            and self.igmp_snooping.querier
            and self.igmp_snooping.querier.enabled
        ):
            logger.warning(
                f"VXLAN '{self.vlan_name}': IGMP snooping querier is a L2 feature, will have no effect in L3 mode."
            )

        if is_l2 and not self.enabled:
            logger.warning(
                f"VXLAN '{self.vlan_name}': VXLAN is in L2 mode, setting enabled to False will have no effect."
            )

        if is_l2 and (self.acl_ipv4_in or self.acl_ipv4_out or self.acl_ipv6_in or self.acl_ipv6_out):
            logger.warning(f"VXLAN '{self.vlan_name}': ACLs are set but VXLAN is in L2 mode, ACLs will have no effect.")

        if is_l2 and self.dhcp_relays:
            logger.warning(
                f"VXLAN '{self.vlan_name}': DHCP relays are set but VXLAN is in L2 mode, DHCP relays will have no effect."
            )

        if is_l2 and self.mtu:
            logger.warning(f"VXLAN '{self.vlan_name}': MTU is set but VXLAN is in L2 mode, MTU will have no effect.")

        return self


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
