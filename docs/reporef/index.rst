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

Additional variables available for distribution switches:

- infra_ip: IPv4 infrastructure VRF address (ex 10.199.0.0)

- infra_ipif: IPv4 infrastructure VRF address inc prefix (ex 10.199.0.0/32)

- vrfs: A list of dictionaries with two keys: "name" and "rd" (rd as in Route Distinguisher).
  Populated from settings defined in routing.yml.

- bgp_ipv4_peers: A list of dictionaries with the keys: "peer_hostname", "peer_infra_lo", "peer_ip" and "peer_asn".
  Contains one entry per directly connected dist/core device, used to build an eBGP underlay for the fabric.
  Populated from the links database table.

- bgp_evpn_peers: A list of dictionaries with the keys: "peer_hostname", "peer_infra_lo", "peer_asn".
  Contains one entry per hostname specified in settings->evpn_spines. Used to build
  eBGP peering for EVPN between loopbacks.

- mgmtdomains: A list of dictionaries with the keys: "ipv4_gw", "vlan", "description", "esi_mac".
  Populated from the mgmtdomains database table.

- asn: A private unique Autonomous System number generated from the last two octets
  of the infra_lo IP address on the device.
 
All settings configured in the settings repository are also exposed to the templates.

settings
--------

Settings are defined at different levels and inherited (possibly overridden) in several steps.
For example, NTP servers might be defined in the "global" settings to impact the entire
managed network, but then overridden for a specific device type that needs custom NTP servers.
The inheritence is defined in these steps: Global -> Core/Dist/Access -> Device specific.
The directory structure looks like this:

- global

  * groups.yml: Definition of custom device groups
  * vxlans.yml: Definition of VXLAN/VLANs
  * routing.yml: Definition of global routing settings like fabric underlay and VRFs
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
    eBGP connections to these devices.

- vrfs:

  * name: The name of the VRF. Should be one word (no spaces).
  * vrf_id: An integer between 1-65535. This ID can be used to generate unique VNI, RD and RT
    values for this VRF.
  * groups: A list of groups this VRF should be provisioned on.

* extroute_static:

  * vrfs:

    * name: Name of the VRF
    * ipv4:

      * destination: IPv4 prefix
      * nexthop: IPv4 nexthop address
      * interface: Exiting interface (optional)
      * name: Name/description of route (optional, defaults to "undefined")
      * cli_append_str: Custom configuration to append to this route (optional)

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
    * neighbor_v4:

      * peer_as: AS number the remote peer
      * peer_ipv4: IPv4 address of peer
      * route_map_in: Route-map to filter incoming routes
      * route_map_out: Route-map to filter outgoing routes
      * description: Description of remote peer (optional, defaults to "undefined")
      * cli_append_str: Custom configuration to append to this peer (optional)
    * neighbor_v6:

      * peer_as: AS number the remote peer
      * peer_ipv6: IPv6 address of peer
      * route_map_in: Route-map to filter incoming routes
      * route_map_out: Route-map to filter outgoing routes
      * description: Description of remote peer (optional, defaults to "undefined")
      * cli_append_str: Custom configuration to append to this peer (optional)

vxlans.yml:

Contains a dictinary called "vxlans", which in turn has one dictinoary per vxlan, vxlan
name is the dictionary key and dictionaly values are:

  * vni: VXLAN ID, 1-16777215
  * vrf: VRF name. Optional unless ipv4_gw is also specified.
  * vlan_id: VLAN ID, 1-4095
  * vlan_name: VLAN name, single word/no spaces, max 31 characters
  * ipv4_gw: IPv4 address with CIDR netmask, ex: 192.168.0.1/24. Optional.
  * groups: List of group names where this VXLAN/VLAN should be provisioned. If you select an
    access switch the parent dist switch should be automatically provisioned.

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
  * ifclass: Interface class, one of: downlink, uplink, custom
  * config: Optional. Raw CLI config used in case "custom" ifclass was selected

etc
---

Configuration files for system daemons

Directory structure:

- dhcpd/

  * dhcpd.conf: Used for ZTP DHCPd
