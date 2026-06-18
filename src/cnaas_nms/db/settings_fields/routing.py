from typing import Annotated, Dict, List, Optional

from pydantic import BaseModel, Field

from cnaas_nms.db.settings_fields.shared import (
    RemovePrivateASEnum,
    accept_or_reject_schema,
    as_num_schema,
    as_num_schema_optional,
    ebgp_multihop_schema,
    hostname_schema,
    ifname_schema,
    ipv4_if_schema,
    ipv4_or_ipv6_if_schema,
    ipv4_schema,
    ipv6_if_schema,
    ipv6_schema,
    maximum_routes_schema,
    prefix_size_or_range_schema,
    vlan_name_schema,
    vrf_id_schema,
)


class f_evpn_peer(BaseModel):
    hostname: str = hostname_schema


class f_vrf(BaseModel):
    name: Optional[str] = None
    vrf_id: int = vrf_id_schema
    import_route_targets: List[str] = []
    export_route_targets: List[str] = []
    import_policy: Optional[str] = None
    export_policy: Optional[str] = None
    groups: List[str] = []


class f_ipv4_static_route(BaseModel):
    destination: str = ipv4_if_schema
    nexthop: str = ipv4_schema
    interface: Optional[str] = ifname_schema
    name: str = "undefined"
    cli_append_str: str = ""


class f_ipv6_static_route(BaseModel):
    destination: str = ipv6_if_schema
    nexthop: str = ipv6_schema
    interface: Optional[str] = ifname_schema
    name: str = "undefined"
    cli_append_str: str = ""


class f_extroute_static_vrf(BaseModel):
    name: str
    ipv4: Optional[List[f_ipv4_static_route]] = None
    ipv6: Optional[List[f_ipv6_static_route]] = None


class f_extroute_static(BaseModel):
    vrfs: List[f_extroute_static_vrf]


class f_extroute_ospfv3_vrf(BaseModel):
    name: str
    ipv4_redist_routefilter: Optional[str] = None
    ipv6_redist_routefilter: Optional[str] = None
    cli_append_str: str = ""


class f_extroute_ospfv3(BaseModel):
    vrfs: List[f_extroute_ospfv3_vrf]


class f_extroute_bgp_neighbor_v4(BaseModel):
    peer_ipv4: str = ipv4_schema
    peer_as: int = as_num_schema
    route_map_in: str = vlan_name_schema
    route_map_out: str = vlan_name_schema
    description: str = "undefined"
    bfd: Optional[bool] = None
    graceful_restart: Optional[bool] = None
    next_hop_self: Optional[bool] = None
    update_source: Optional[str] = ifname_schema
    ebgp_multihop: Optional[int] = ebgp_multihop_schema
    maximum_routes: Optional[int] = maximum_routes_schema
    auth_type: Optional[str] = None
    auth_string: Optional[str] = None
    remove_private_as: Optional[RemovePrivateASEnum] = None
    cli_append_str: str = ""


class f_extroute_bgp_neighbor_v6(BaseModel):
    peer_ipv6: str = ipv6_schema
    peer_as: int = as_num_schema
    route_map_in: str = vlan_name_schema
    route_map_out: str = vlan_name_schema
    description: str = "undefined"
    bfd: Optional[bool] = None
    graceful_restart: Optional[bool] = None
    next_hop_self: Optional[bool] = None
    update_source: Optional[str] = ifname_schema
    ebgp_multihop: Optional[int] = ebgp_multihop_schema
    maximum_routes: Optional[int] = maximum_routes_schema
    auth_type: Optional[str] = None
    auth_string: Optional[str] = None
    remove_private_as: Optional[RemovePrivateASEnum] = None
    cli_append_str: str = ""


class f_extroute_bgp_vrf(BaseModel):
    name: str
    local_as: int = as_num_schema
    neighbor_v4: List[f_extroute_bgp_neighbor_v4] = []
    neighbor_v6: List[f_extroute_bgp_neighbor_v6] = []
    cli_append_str: str = ""


class f_extroute_bgp(BaseModel):
    vrfs: List[f_extroute_bgp_vrf] = []


class f_underlay(BaseModel):
    infra_lo_net: str = ipv4_if_schema
    infra_link_net: str = ipv4_if_schema
    mgmt_lo_net: str = ipv4_if_schema
    bgp_asn: Optional[int] = as_num_schema_optional


class f_prefixset_item(BaseModel):
    prefix: str = ipv4_or_ipv6_if_schema
    masklength_range: Optional[Annotated[int, Field(ge=0, le=128)] | Annotated[str, prefix_size_or_range_schema]] = None


class f_prefixset(BaseModel):
    mode: str = "ipv4"
    prefixes: List[f_prefixset_item]


class f_rpolicy_condition(BaseModel):
    match_type: str
    match_target: str


class f_rpolicy_statement(BaseModel):
    action: str = accept_or_reject_schema
    conditions: List[f_rpolicy_condition]


class f_routingpolicy(BaseModel):
    statements: List[f_rpolicy_statement]


class f_routing(BaseModel):
    vrfs: List[f_vrf] = []
    underlay: Optional[f_underlay] = None
    evpn_peers: List[f_evpn_peer] = []
    extroute_static: Optional[f_extroute_static] = None
    extroute_ospfv3: Optional[f_extroute_ospfv3] = None
    extroute_bgp: Optional[f_extroute_bgp] = None
    prefix_sets: Dict[str, f_prefixset] = {}
    routing_policies: Dict[str, f_routingpolicy] = {}
    # This is defined both in f_base_system and f_routing
    external_routing_policies: List[str] = []
