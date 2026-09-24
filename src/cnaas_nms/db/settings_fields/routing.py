from ipaddress import IPv4Address, IPv4Interface, IPv6Address, IPv6Interface
from typing import Annotated

from annotated_types import Ge, Le
from pydantic import BaseModel, StringConstraints

from cnaas_nms.db.settings_fields.shared import (
    AcceptReject,
    AsNum,
    EBGPMultihop,
    HostName,
    InterfaceName,
    MaximumRoutes,
    NetName,
    RemovePrivateASEnum,
    VrfId,
)


class f_evpn_peer(BaseModel):
    hostname: HostName


class f_vrf(BaseModel):
    name: str | None = None
    vrf_id: VrfId
    import_route_targets: list[str] = []
    export_route_targets: list[str] = []
    import_policy: str | None = None
    export_policy: str | None = None
    groups: list[str] = []


class f_ipv4_static_route(BaseModel):
    destination: IPv4Interface
    nexthop: IPv4Address
    interface: InterfaceName | None = None
    name: str = "undefined"
    cli_append_str: str = ""


class f_ipv6_static_route(BaseModel):
    destination: IPv6Interface
    nexthop: IPv6Address
    interface: InterfaceName | None = None
    name: str = "undefined"
    cli_append_str: str = ""


class f_extroute_static_vrf(BaseModel):
    name: str
    ipv4: list[f_ipv4_static_route] | None = None
    ipv6: list[f_ipv6_static_route] | None = None


class f_extroute_static(BaseModel):
    vrfs: list[f_extroute_static_vrf]


class f_extroute_ospfv3_vrf(BaseModel):
    name: str
    ipv4_redist_routefilter: str | None = None
    ipv6_redist_routefilter: str | None = None
    cli_append_str: str = ""


class f_extroute_ospfv3(BaseModel):
    vrfs: list[f_extroute_ospfv3_vrf]


class f_extroute_bgp_neighbor_v4(BaseModel):
    peer_ipv4: IPv4Address
    peer_as: AsNum
    route_map_in: NetName
    route_map_out: NetName
    description: str = "undefined"
    bfd: bool | None = None
    graceful_restart: bool | None = None
    next_hop_self: bool | None = None
    update_source: InterfaceName | None = None
    ebgp_multihop: EBGPMultihop | None = None
    maximum_routes: MaximumRoutes | None = None
    auth_type: str | None = None
    auth_string: str | None = None
    remove_private_as: RemovePrivateASEnum | None = None
    cli_append_str: str = ""


class f_extroute_bgp_neighbor_v6(BaseModel):
    peer_ipv6: IPv6Address
    peer_as: AsNum
    route_map_in: NetName
    route_map_out: NetName
    description: str = "undefined"
    bfd: bool | None = None
    graceful_restart: bool | None = None
    next_hop_self: bool | None = None
    update_source: InterfaceName | None = None
    ebgp_multihop: EBGPMultihop | None = None
    maximum_routes: MaximumRoutes | None = None
    auth_type: str | None = None
    auth_string: str | None = None
    remove_private_as: RemovePrivateASEnum | None = None
    cli_append_str: str = ""


class f_extroute_bgp_vrf(BaseModel):
    name: str
    local_as: AsNum
    neighbor_v4: list[f_extroute_bgp_neighbor_v4] = []
    neighbor_v6: list[f_extroute_bgp_neighbor_v6] = []
    cli_append_str: str = ""


class f_extroute_bgp(BaseModel):
    vrfs: list[f_extroute_bgp_vrf] = []


class f_underlay(BaseModel):
    infra_lo_net: IPv4Interface
    infra_link_net: IPv4Interface
    mgmt_lo_net: IPv4Interface
    bgp_asn: AsNum | None = None


class f_prefixset_item(BaseModel):
    prefix: IPv4Interface | IPv6Interface
    masklength_range: (
        Annotated[int, Ge(0), Le(128)]
        | Annotated[str, StringConstraints(pattern=r"^[0-9]{1,3}([-][0-9]{1,3})?$")]
        | None
    ) = None


class f_prefixset(BaseModel):
    mode: str = "ipv4"
    prefixes: list[f_prefixset_item]


class f_rpolicy_condition(BaseModel):
    match_type: str
    match_target: str


class f_rpolicy_statement(BaseModel):
    action: AcceptReject
    conditions: list[f_rpolicy_condition]


class f_routingpolicy(BaseModel):
    statements: list[f_rpolicy_statement]


class f_routing(BaseModel):
    vrfs: list[f_vrf] = []
    underlay: f_underlay | None = None
    evpn_peers: list[f_evpn_peer] = []
    extroute_static: f_extroute_static | None = None
    extroute_ospfv3: f_extroute_ospfv3 | None = None
    extroute_bgp: f_extroute_bgp | None = None
    prefix_sets: dict[str, f_prefixset] = {}
    routing_policies: dict[str, f_routingpolicy] = {}
    # This is defined both in f_base_system and f_routing
    external_routing_policies: list[str] = []
