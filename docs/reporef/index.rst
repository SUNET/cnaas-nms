Repository Reference
====================

Templates
---------

Templates for switch configurations.

In the base of this repository there should be one directory for each network operating system
platform, like "eos", "junos" or "iosxr".

In each of these directories there needs to be a file called "mapping.yml", this file defines
what template files should be used for each device type. For example, in mapping.yml there
might be a definition of templates for an access switch specified like this:

::

    ACCESS:
        entrypoint: access.j2
        dependencies:
            - managed-full.j2


This indicates that the starting point for the template of access switches for this platform
is deffined in the Jinja2 template file called "access.j2". Additionally, this template file
will depend on things defined in a file called "managed-full.j2".

The template files themselves are written using the Jinja2 templating language. Variables
that are exposed from CNaaS includes:

- hostname: Short hostname of device

- host: Short hostname of device (implicitly added by nornir-jinja2)

- mgmt_ip: IPv4 management address (ex 192.168.0.10)

- mgmt_ipif: IPv4 management address including prefix length (ex 192.168.0.10/24)

- mgmt_prefixlen: Just the prefix length (ex 24)

- mgmt_vlan_id: VLAN id for management (ex 10)

- mgmt_gw: IPv4 address for the default gateway in the management network

- uplinks: A list of uplink interfaces, each interface is a dictionary with these keys:

  * ifname: Name of the physical interface (ex Ethernet1)

- access_auto: A list of access_auto interfacs. Using same keys as uplinks.

- device_model: Device model string, same as "model" in the device API. Can be
  used if you need model specific configuration lines.

- device_os_version: Device OS version string, same as "os_version" in the
  device API. Can be used if you need OS version specific configuration lines.

- device_id: CNaaS-NMS internal ID number of the device

Additional variables available for distribution switches:

- infra_ip: IPv4 infrastructure VRF address (ex 10.199.0.0)

- infra_ipif: IPv4 infrastructure VRF address inc prefix (ex 10.199.0.0/32)

- vrfs: A list of dictionaries with two keys: "name" and "rd" (rd as in Route Distinguisher).
  Populated from settings defined in routing.yml.

- bgp_ipv4_peers: A list of dictionaries with the keys: "peer_hostname", "peer_infra_lo", "peer_ip" and "peer_asn".
  Contains one entry per directly connected dist/core device, used to build an eBGP underlay for the fabric.
  Populated from the links database table.

- bgp_evpn_peers: A list of dictionaries with the keys: "peer_hostname", "peer_infra_lo", "peer_asn".
  Contains one entry per hostname specified in settings->evpn_peers. Used to build
  eBGP peering for EVPN between loopbacks.

- mgmtdomains: A list of dictionaries with the keys: "ipv4_gw", "vlan", "description", "esi_mac".
  Populated from the mgmtdomains database table.

- asn: A private unique Autonomous System number generated from the last two octets
  of the infra_lo IP address on the device.
 
All settings configured in the settings repository are also exposed to the templates.

.. _settings_repo_ref:

settings
--------

Settings are defined at different levels and inherited (possibly overridden) in several steps.
For example, NTP servers might be defined in the "global" settings to impact the entire
managed network, but then overridden for a specific device type that needs custom NTP servers.
The inheritence is defined in these steps: Global -> Core/Dist/Access -> Device specific.
The directory structure looks like this:

- global

  * groups.yml: Definition of custom device groups
  * routing.yml: Definition of global routing settings like fabric underlay and VRFs
  * vxlans.yml: Definition of VXLAN/VLANs
  * base_system.yml: Base system settings

- core

  * base_system.yml: Base system settings
  * interfaces_<model>.yml: Model specific default interface settings

- dist

  * base_system.yml: Base system settings
  * interfaces_<model>.yml: Model specific default interface settings

- access:

  * base_system.yml: Base system settings

- devices:

  * <hostname>

    + base_system.yml
    + interfaces.yml
    + routing.yml

groups.yml:

Contains a dictionary named "groups", that contains a list of groups.
Each group is defined as a dictionary with a single key named "group",
and that key contains a dictionary with two keys:

- name: A string representing a name. No spaces.
- regex: A Python style regex that matches on device hostnames

All devices that matches the regex will be included in the group.

::

   ---
   groups:
     - group:
         name: 'ALL'
         regex: '.*'
     - group:
         name: 'BORDER_DIST'
         regex: '(south-dist0[1-2]|north-dist0[1-2])'
     - group:
         name: 'DIST_EVEN'
         regex: '.*-dist[0-9][02468]'
     - group:
         name: 'DIST_ODD'
         regex: '.*-dist[0-9][13579]'

routing.yml:

Can contain the following dictionaries with specified keys:

- underlay:

  * infra_link_net: A /16 of IPv4 addresses that CNaaS-NMS can use to automatically assign
    addresses for infrastructure links from (ex /31 between dist-core).
  * infra_lo_net: A /16 of IPv4 addresses that CNaaS-NMS can use to automatically assign
    addresses for infrastructure loopback interfaces from.
  * mgmt_lo_net: A subnet for management loopbacks for dist/core devices.

- evpn_peers:

  * hostname: A hostname of a CORE (or DIST) device from the device database.
    The other DIST switches participating in the VXLAN/EVPN fabric will establish
    eBGP connections to these devices. If an empty list is provided all CORE
    devices will be added as evpn_peers instead.

- vrfs:

  * name: The name of the VRF. Should be one word (no spaces).
  * vrf_id: An integer between 1-65535. This ID can be used to generate unique VNI, RD and RT
    values for this VRF.
  * groups: A list of groups this VRF should be provisioned on.
  * import_route_targets: A list of strings containing extra route targets to import
    for route leaking (optional)
  * export_route_targets: A list of strings containing extra route targets to export
    for route leaking (optional)
  * import_policy: A string containing route policy/route map to define import
    behavior, useful in route leaking scenarios (optional)
  * export_policy: A string containing route policy/route map to define export
    behavior, useful in route leaking scenarios (optional)

* extroute_static:

  * vrfs:

    * name: Name of the VRF
    * ipv4:

      * destination: IPv4 prefix
      * nexthop: IPv4 nexthop address
      * interface: Exiting interface (optional)
      * name: Name/description of route (optional, defaults to "undefined")
      * cli_append_str: Custom configuration to append to this route (optional)

    * ipv6:

      * destination: IPv6 prefix
      * nexthop: IPv6 nexthop address
      * other options are the same as ipv4

* extroute_ospfv3:

  * vrfs:

    * name: Name of the VRF
    * ipv4_redist_routefilter: Name of a route filter (route-map) that filters what should be redistributed into OSPF
    * ipv6_redist_routefilter: Name of a route filter (route-map) that filters what should be redistributed into OSPF
    * cli_append_str: Custom configuration to add for this VRF (optional)

* extroute_bgp:

  * vrfs:

    * name: Name of the VRF
    * local_as: AS number that CNaaS NMS devices will present themselves as
    * cli_append_str: Custom configuration to append to BGP VRF config (optional)
    * neighbor_v4:

      * peer_as: AS number the remote peer
      * peer_ipv4: IPv4 address of peer
      * route_map_in: Route-map to filter incoming routes
      * route_map_out: Route-map to filter outgoing routes
      * ebgp_multihop: Configure eBGP multihop/TTL security, integer 1-255
      * bfd: Set to true to enable Bidirectional Forward Detection (BFD)
      * graceful_restart: Set to true to enable capability graceful restart
      * next_hop_self: Set to true to always advertise this router's address as the BGP next hop
      * maximum_routes: Maximum routes to receive from peer, integer 0-4294967294
      * update_source: Specify local source interface for the BGP session
      * auth_string: String used to calculate MD5 hash for authentication (password)
      * description: Description of remote peer (optional, defaults to "undefined")
      * cli_append_str: Custom configuration to append to this peer (optional)
    * neighbor_v6:

      * peer_ipv6: IPv6 address of peer
      * other options are the same as neighbor_v4

routing.yml examples:

::

   ---
   extroute_bgp:
     vrfs:
       - name: OUTSIDE
         local_as: 64667
         neighbor_v4:
           - peer_ipv4: 10.0.255.1
             peer_as: 64666
             route_map_in: fw-lab-in
             route_map_out: default-only-out
             description: "fw-lab"
             bfd: true
             graceful_restart: true
   extroute_static:
     vrfs:
       - name: MGMT
         ipv4:
           - destination: 172.12.0.0/24
             nexthop: 10.0.254.1
             name: cnaas-mgmt

vxlans.yml:

Contains a dictinary called "vxlans", which in turn has one dictinoary per vxlan, vxlan
name is the dictionary key and dictionaly values are:

  * vni: VXLAN ID, 1-16777215
  * vrf: VRF name. Optional unless ipv4_gw is also specified.
  * vlan_id: VLAN ID, 1-4095
  * vlan_name: VLAN name, single word/no spaces, max 31 characters
  * ipv4_gw: IPv4 gateway address in CIDR notation, ex: 192.168.0.1/24. Optional.
  * ipv4_secondaries: List of IPv4 addresses in CIDR notation. Optional.
  * ipv6_gw: IPv6 address, ex: fe80::1. Optional.
  * dhcp_relays: DHCP relay address. Optional.
  * mtu: Define custom MTU. Optional.
  * acl_ipv4_in: Access control list to apply for ingress IPv4 traffic to routed interface. Optional.
  * acl_ipv4_out: Access control list to apply for egress IPv4 traffic from routed interface. Optional.
  * acl_ipv6_in: Access control list to apply for ingress IPv6 traffic to routed interface. Optional.
  * acl_ipv6_out: Access control list to apply for egress IPv6 traffic from routed interface. Optional.
  * cli_append_str: Optional. Custom configuration to append to this interface.
  * tags: List of custom strings to tag this VXLAN with. Optional.
  * groups: List of group names where this VXLAN/VLAN should be provisioned. If you select an
    access switch the parent dist switch should be automatically provisioned.
  * devices: List of device names where this VXLAN/VLAN should be provisioned. Optional.

interfaces.yml:

For dist and core devices interfaces are configured in YAML files. The
interface configuration can either be done per device, or per device model.
If there is a device specific folder under devices/ then the model
interface settings will be ignored. Model specific YAML files
should be named like the device model as listed in the devices API, but in
all lower-case and with all whitespaces replaced with underscore ("_").

Keys for interfaces.yml or interfaces_<model>.yml:

* interfaces: List of dicctionaries with keys:

  * name: Interface name, like "Ethernet1"
  * ifclass: Interface class, one of: downlink, fabric, custom, port_template_*
  * config: Optional. Raw CLI config used in case "custom" ifclass was selected

* Additional interface options for port_template type:

  * untagged_vlan: Optional. Numeric VLAN ID for untagged frames.
  * tagged_vlan_list: Optional. List of allowed numeric VLAN IDs for tagged frames.
  * description: Optional. Description for the interface, this should be a string 0-64 characters.
  * enabled: Optional. Set the administrative state of the interface. Defaults to true if not set.
  * aggregate_id: Optional. Identifier for configuring LACP etc. Integer value.
    Special value -1 means configure MLAG and use ID based on indexnum.
  * cli_append_str: Optional. Custom configuration to append to this interface. 

The "downlink" ifclass is used on DIST devices to specify that this interface
is used to connect access devices. The "fabric" ifclass is used to specify that
this interface is used to connect DIST or CORE devices with each other to form
the switch (vxlan) fabric. Linknet data will only be configured on interfaces
specified as "fabric". If no linknet data is available in the database then
the fabric interface will be configured for ZTP of DIST/CORE devices by
providing DHCP (relay) access.
"port_template_*" is used to specify a user defined port template. This can then
be used to apply some site-specific configuration via Jinja templates. For
example specify "port_template_hypervisor" and build a corresponding Jinja
template by matching on that ifclass.

base_system.yml:

Contains base system settings like:

- ntp_servers
- snmp_servers
- dns_servers
- syslog_servers
- flow_collectors
- dhcp_relays
- internal_vlans
- dot1x_fail_vlan: Numeric ID of authentication fail VLAN

Example of base_system.yml:

::

   ---
   ntp_servers:
     - host: 10.255.0.1
     - host: 10.255.0.2
   snmp_servers:
     - host: 10.255.0.11
   dns_servers:
     - host: 10.255.0.1
     - host: 10.255.0.2
   syslog_servers:
     - host: 10.255.0.21
     - host: 10.255.0.22
   flow_collectors:
     - host: 10.255.0.30
       port: 6343
   dhcp_relays:
     - host: 10.255.1.1
     - host: 10.255.1.2
   internal_vlans:
     vlan_id_low: 3006
     vlan_id_high: 4094
   dot1x_fail_vlan: 13


syslog_servers and radius_severs can optionally have the key "port" specified
to indicate a non-defalut layer4 (TCP/UDP) port number.

internal_vlans can optionally be specified if you want to manually define
the range of internal VLANs on L3 switches. You can also specify the option
"allocation_order" under internal_vlans which is a custom string that defaults
to "ascending". If internal_vlans is specified then a collision check will
be performed for any defined vlan_ids in vxlans settings.

etc
---

Configuration files for system daemons

Directory structure:

- dhcpd/

  * dhcpd.conf: Used for ZTP DHCPd
