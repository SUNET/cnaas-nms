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

- stack_members: CNaaS-NMS stack members if they are include. Each stackmember has a hardware id, and member number, priority is optional.

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
The inheritence is defined in these steps:
Global -> Fabric -> Core/Dist/Access -> Group -> Device specific.
The directory structure looks like this:

- global

  * groups.yml: Definition of custom device groups
  * routing.yml: Definition of global routing settings like fabric underlay and VRFs
  * vxlans.yml: Definition of VXLAN/VLANs
  * base_system.yml: Base system settings

- fabric (core+dist)

  * base_system.yml: Base system settings

- core

  * base_system.yml: Base system settings
  * interfaces_<model>.yml: Model specific default interface settings

- dist

  * base_system.yml: Base system settings
  * interfaces_<model>.yml: Model specific default interface settings

- access:

  * base_system.yml: Base system settings

- groups:

  * <group name>

    + base_system.yml
    + interfaces.yml
    + routing.yml

- devices:

  * <hostname>

    + base_system.yml
    + interfaces.yml
    + routing.yml

groups.yml:

A device in CNaaS-NMS will be a member of exactly one primary group, and
optionally any number of secandary groups. Primary groups can be used to
configure settings per group. Secondary groups can be used to assign VXLAN
memberships, select devices for synchronization or firmware upgrade etc.

groups.yml contains a dictionary named "groups", that contains a list of groups.
Each group is defined as a dictionary with a single key named "group",
and that key contains a dictionary with two keys:

- name: A string representing a name. No spaces.
- regex: A Python style regex that matches on device hostnames.
- group_priority: Optional integer value 0-100. Specifies which group should
  have the highest priority when determining the primary group for a device.
  Higher value means higher priority. Defaults to 0, value of 1 is reserved
  for builtin group DEFAULT.
- templates_branch: Optional string that specifies an alternative git branch
  in the templates repository to use for devices in this primary group. Make
  sure the branch exists in the templates repository and that the templates
  repository is refreshed before setting this value or you will get an error.

There will always exist a group called DEFAULT with group_priority 1 even
if it's not specified in groups.yml.

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
     - group:
         name: 'E1'
         regex: 'eosdist1$'
         group_priority: 100
         templates_branch: "new_dist_features"
     - group:
         name: 'E'
         regex: 'eosdist.*'
         group_priority: 99


routing.yml:

Can contain the following dictionaries with specified keys:

- underlay:

  * infra_link_net: A /16 of IPv4 addresses that CNaaS-NMS can use to automatically assign
    addresses for infrastructure links from (ex /31 between dist-core).
  * infra_lo_net: A /16 of IPv4 addresses that CNaaS-NMS can use to automatically assign
    addresses for infrastructure loopback interfaces from.
  * mgmt_lo_net: A subnet for management loopbacks for dist/core devices.
  * bgp_asn: Optional BGP autonomous system number, useful for iBGP underlay.

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
      * remove_private_as: Optional, if set must be either "all" or "replace".
        Remove all private AS numbers from AS_PATH, or replace private AS numbers with local AS.
      * cli_append_str: Custom configuration to append to this peer (optional)
    * neighbor_v6:

      * peer_ipv6: IPv6 address of peer
      * other options are the same as neighbor_v4

- prefix_sets: Dictionary of {<name>, <entry>}:

  * mode: String, either "ipv4", "ipv6" or "mixed"
  * prefixes: list of

    * prefix: String for ipv4 or ipv6 prefix, ex: 10.0.0.0/8
    * masklength_range: Optional string defining range of prefixes to match, ex: 24-32 or 32-32

- routing_policies: Dictionary of {<name>, <entry>}:

  * statements: List of:

    * action: Action to perform on match, either "accept" or "reject"
    * conditions: List of:

      * match_type: String, ex "ipv4 prefix-set"
      * match_target: String, referring to prefix-set for example: "default-route"

- external_routing_policies: List of strings, referring to routing policies defined in external
  sources such as templates repository. BGP neighbor route maps must refer to a policy defined in
  either this list or the routing_policies setting described above.


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
   prefix_sets:
     "default":
       mode: "ipv4"
       prefixes:
         - prefix: 0.0.0.0/0
           masklength_range: 0
     "24_or_longer":
       mode: "ipv4"
       prefixes:
         - prefix: 0.0.0.0/0
           masklength_range: 24-32
     "v6default":
       mode: "ipv6"
       prefixes:
         - prefix: ::/0
     "all-ipv6":
       mode: "ipv6"
       prefixes:
         - prefix: ::/0
           masklength_range: 0-128
   routing_policies:
     "allow_default":
       statements:
         - action: "accept"
           conditions:
             - match_type: "ipv4 prefix-set"
               match_target: "default"
     "allow_all_v6":
       statements:
         - action: "accept"
           conditions:
             - match_type: "ipv6 prefix-set"
               match_target: "all-ipv6"

vxlans.yml:

Contains a dictinary called "vxlans", which in turn has one dictinoary per vxlan, vxlan
name is the dictionary key and dictionaly values are:

- vxlans: Dictionary of {<name>, <entry>}:

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

  * name: Interface name, like "Ethernet1". Can also be an interface range like "Ethernet[1-4]".
  * ifclass: Interface class, one of: downlink, fabric, custom, mirror, port_template_*
  * config: Optional. Raw CLI config used in case "custom" ifclass was selected

* Additional interface options for port_template type:

  * untagged_vlan: Optional. Numeric VLAN ID for untagged frames.
  * tagged_vlan_list: Optional. List of allowed VLAN IDs, can be single values or ranges, ex: [1, 5, "10-15"]
  * description: Optional. Description for the interface, this should be a string 0-64 characters.
  * enabled: Optional. Set the administrative state of the interface. Defaults to true if not set.
  * aggregate_id: Optional. Identifier for configuring LACP etc. Integer value.
    Special value -1 means configure MLAG and use ID based on indexnum.
  * tags: Optional list of strings, custom user defined tags to apply.
  * vrf: Optional VRF instance, must be specified if IP adress is specified
  * ipv4_address: Optional IPv4 address for the interface
  * ipv6_address: Optional IPv6 address for the interface
  * mtu: Optional integer specifying MTU size
  * acl_ipv4_in: Access control list to apply for ingress IPv4 traffic to interface. Optional.
  * acl_ipv4_out: Access control list to apply for egress IPv4 traffic from interface. Optional.
  * acl_ipv6_in: Access control list to apply for ingress IPv6 traffic to interface. Optional.
  * acl_ipv6_out: Access control list to apply for egress IPv6 traffic from interface. Optional.
  * metric: Optional integer specifying metric for this interface.
  * cli_append_str: Optional. Custom configuration to append to this interface.

* For downlink and fabric type ports these options are available with same function as above:

  * aggregate_id
  * enabled
  * cli_append_str
  * metric
  * mtu
  * tags

*  For mirror type ports these options are available with same function as above:

  * description
  * enabled


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
"mirror" ifclass can be used on DIST devices that are part of the same management
domain to copy interface settings from one device to the other, this way you
don't have to maintain the list of allowed vlans on both devices for example.
On one device you configure ports normally with port_template or custom ifclass,
and on the other device in the same management domain you can use ifclass mirror
without any other settings (but you can optionally override description and enabled
status).

base_system.yml:

Contains base system settings like:

- ntp_servers: List of

  * host: IP address or hostname of NTP server

- radius_servers: List of

  * host: IP address or hostname of RADIUS server
  * port: Port number. Optional

- snmp_servers: List of

  * host: IP address or hostname of SNMP trap target
  * port: Port number. Optional

- dns_servers: List of

  * host: IP address to DNS server

- syslog_servers: List of

  * host: IP address or hostname to syslog server
  * port: Port number. Optional

- flow_collectors: List of

  * host: IP address or hostname to flow collector
  * port: Port number. Optional

- dhcp_relays: List of

  * host: IP address or hostname to DHCP relay

- users: List of

  * username: Username string
  * ssh_key: SSH public key string. Optional
  * uid: UserID number. Optional
  * password_hash_arista: Hashed password string for Arista devices. Optional
  * password_hash_cisco: Hashed password string for Cisco devices. Optional
  * password_hash_juniper: Hashed password string for Juniper devices. Optional
  * permission_arista: String to specify user access level for Arista, ex "privilege 15 role network-admin". Optional
  * permission_cisco: String to specify user access level for Cisco, ex "privilege 15". Optional
  * permission_juniper: String to specify user access level for Juniper, ex "superuser". Optional
  * groups: A list of device groups that this user should be provisioned on

- internal_vlans:

  * vlan_low: Low end of internal VLAN range
  * vlan_high: High end of internal VLAN range
  * allocation_order: Allocation order, default "ascending"

- dot1x_fail_vlan: Numeric ID of authentication fail VLAN
- dot1x_multi_host: Allow multiple clients behind a dot1x authenticated port. Default false
- poe_reboot_maintain: Maintain POE supply during reboot of the switch. Default false
- organization_name: Free format string describing organization name
- domain_name: DNS domain (suffix)
- interface_tag_options: Dictionary of {<name>, {description: <description>, groups: <list of groups>}:

  * name: Name of the tag, as defined in templates
  * description: Description of the tag to be displayed in WebUI etc.
  * groups: Optional list of groups where tag should be limited to

- port_template_options: Dictionary of {<name>, {description: <description>, groups: <list of groups>,
  vlan_option: <vlan_option>}:

  * name: Name of the port_template, as defined in templates but without "port_template_" prefix
  * description: Description of the port template to be displayed in WebUI etc.
  * vlan_option: VLAN option to be used for this port template, default "tagged" but can be "untagged"
  or "none". This describes if untagged_vlan or tagged_vlan_list settings should be used for this
  port template.
  * groups: Optional list of groups where port template should be limited to

- vxlan_vni_range: Define a range of VNIs to be used for VXLANs, ex "10000-99999". If any VXLANs are
  configured with VNIs outside of this range an error will be raised when refreshing settings.
- arista_models_32bit: Optional list of strings of Arista models that should be upgraded with 32-bit
  firmware instead of the default 64-bit firmware when using "detect_arch-" keyword in the filename
  parameter to /firmware/upgrade API endpoint. If not specified use list of models provided by NMS.
  If set to empty list always use 64-bit firmware.
- upgrade_post_waittime: Optional dictionary of {<string>, <waittime>} to specify a how long to wait
  after upgrade before testing if the upgrade was successful, waittime is specified in seconds.
  String can be a model number, a platform or "default". If matching model is found, that wait time
  will be used, otherwise if matching platform is found that wait time will be used, otherwise
  default wait time will be used.

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
