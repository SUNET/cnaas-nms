Changelog
=========

Version 1.6.0
-------------

New features:

 - Single-sign on (SSO) via OIDC, enabled via config options in auth_config.yml
 - Role-based access control (RBAC) for API endpoints configured via permissions.yml
 - Logging for refresh settings action includes jobid so it can be filtered for displaying in webUI etc
 - Allow setting aggregate_id, metric, enabled, tags etc on fabric interfaces

Bug fixes:

 - Update device syncstatus if primary group settings file changed (#325)
 - ZTP of dualstack switches (#341)
 - Fix job status change events for refresh jobs (#352)
 - Fix initcheck fabric device proposed linknet IPs (#355)
 - Clean up device init failed job results and make more consistent (#358)
 - Fix for FQDN checks in settings (#343)

Changes:

 - Python upgraded to version 3.11
 - NAPALM upgraded to 5.0, support for Arista EOS 4.22 and earlier has been dropped
 - Initial tables will be created when api container starts, no need for seed sql file for postgres container
 - uwsgi has four processes for http and one process for websocket, api should be more responsive for concurrent http connections

Version 1.5.1
-------------

Bug fixes:

  - Fix commit confirm mode 0 for EOS
  - Update documentation for redundant_link

Version 1.5.0
-------------

New features:

 - Add commit confirm modes: mode 0 - no commit confirm (previous behavior), mode 1 - confirm each device individually
   after it has commited, mode 2 - confirm devices only when all devices in the job has comitted successfully
 - Add API to query configured API settings
 - New settings for:
  * users: username, ssh_key, password_hash etc to handle device user accounts
  * dot1x_multi_host, poe_reboot_maintain
  * prefix_sets and routing_policies to describe policies for router peerings etc
 - Sync history events, save what event caused devices to become unsynchronized
 - API to query running config

Bug fixes:

 - Don't return duplicates of neighbor entries
 - Fix error "Error in repository: HEAD is a detached" when refreshing settings repo
 - Mark init neighbors as unsync if they have local changes
 - Log events was not always sent from redis to websocket

Version 1.4.2
-------------

Bug fixes:

 - Fix ZTP of access switch connected to another access switch with type downlink but empty data

Version 1.4.1
-------------

Bug fixes:

 - Fixed interface range expansion logic for downlink ports during init
 - Allow setting of untagged_vlan to null in interfaces API (#290)
 - Fix duplicate generation of underlay BGP peers (#291)

Version 1.4.0
-------------

New features:

 - Allow ZTP init of access switches with non-redundant uplinks to other access switch via non_redundant option
 - Each device can belong to a primary group, and settings can be defined (overridden) per primary group.
   Inheritence levels are now Global -> Fabric -> Core/Dist/Access -> Group -> Device specific
 - Support interface range expressions like Ethernet[10-11] in settings device interface config
 - Save last know working settings commit, so we can revert if last commit contains errors
   (only saved in memory, not persistent across reboots)
 - Allow sync of devices with multiple links between same peers.
 - Allow updating of neighbor_id on interface (useful if manually changing uplink connections)
 - device_id variable is accessible at template rendering, host and hostname variables documented
 - New settings: organization_name, domain_name, underlay->bgp_asn
 - New jinja filters: different base-encodings, hashes, netutils for IP, MAC, ASNs etc
 - New global config settings:
  * global_unique_vlans: If True VLAN IDs has to be globally unique, if False
    different DIST switches can reuse same VLAN IDs for different L2 domains.
    Defaults to True.
  * init_mgmt_timeout: Timeout to wait for device to apply changed management IP.
    Defaults to 30, specified in seconds (integer).
 - Initial work on API to set/update and get stack members. Not working for ZTP init yet.
 - Linknet API updated to allow PUT/update, allow GET of single linknet, DELETE syntax harmonized with rest of API

Bug fixes:

 - Recalculate group memberships after ZTP init.
 - Mark neighbors as unsynchronized after deleting a device.
 - If device is not reachable on new IP after ZTP init, then change back to use old IP so we can
   attempt new ZTP init later.
 - Restore previous config version apply bug fixed.
 - Allow resetting entire interfaca data to null, instead of having to specify each value as null.
 - During ZTP init, don't update and save linknets unless device can actually proceed with ZTP.

Version 1.3.2
-------------

Bug fixes:

 - Fix for ZTP init of dist devices (#219,#218)

Version 1.3.1
-------------


New features:

 - New settings for vxlans: acl_ipv4_in, acl_ipv4_out, acl_ipv6_in, acl_ipv6_out, cli_append_str
 - New data options in interfaces API: bpdu_filter, tags, cli_append_str

Version 1.3.0
-------------

New features:

 - CNaaS specific Jinja2 filters: increment_ip, ipv4_to_ipv6, isofy_ipv4 (#167)
 - "aggregate_id" option for access ports to build link aggregates from access switches (#171)
 - New settings for: flow_collectors, route leaking, port_template, dot1x_fail_vlan, vxlan tags, ipv4_secondaries (#178,#192,#193,#194,#195,#196,#203)
 - Automatic descriptions for ACCESS_DOWNLINK type ports (#189)
 - Option to filter job result output fields in API response (#197)

Bug fixes:

 - Fix race condition issue where different threads could sometimes cause issues with
   wrong template being used when syncing multiple different operating systems in same job (#168,#176)
 - Fix validation and return output for mgmtdomains API (#177)
 - Cleanup of docker images (#184,#185,#186,#191)
 - Update device last_seen on syncto, update facts, firmware post flight, device discovered, init step2 (#198)
 - Fix factory_default: false (#200)
 - Fix assigning of vxlans etc to both groups and devices at same time (#201)
 - Possible fix for "weak object has gone away" (#205)
 - Fixes for device synchranization status updating (#208,#209)

Version 1.2.1
-------------

Bugfix release.

Bug fixes:

- Fix for ZTP of fabric devices when INIT and DISCOVERED passwords are different
- Fix for mgmt_ip variable at initial fabric device sync
- Better init check error message
- Documentation fix
- Include groups with no devices in listing

Version 1.2.0
-------------

New features:

- ZTP support for core and diste devices (#137)
- Init check API call to test if device is compatible for ZTP without commit (#136, #156)
- Option to have model-specific default interface settings (#135)
- Post-flight check for firmware upgrade (#139)
- Abort scheduled jobs, best-effort abort of running jobs (#142)
- API call to update existing interfaces on device after ZTP (#155)
- More settings for external BGP routing, DNS servers, internal VLANs (#143, #146, #152)
- Install NMS issued certificate on new devices during ZTP (#149)
- Switch to Nornir 3.0, improved whitespace rendering in templates (#148)

Bug fixes:

- Fix blocking websockets (#138)
- Fix access downlink port detection (#141)
- Post upgrade confighash mismatch (#145)
- Discover device duplicate jobs improvements (#151)
- Trim facts fields before saving in database (#153)

Version 1.1.0
-------------

New features:

- New options for connecting access switches:

  - Two access switches as an MLAG pair
  - Access switch connected to other access switch

- New template variables:

  - device_model: Hardware model of this device
  - device_os_version: OS version of this device

- Get/restore previous config versions for a device
- API call to update facts (serial,os version etc) about device
- Websocket event improvements for logs, jobs and device updates

Version 1.0.0
-------------

New features:

- Syncto for core devices
- Access interface updates via API calls, "port bounce"
- Static, BGP and OSPF external routing template support
- eBGP / EVPN fabric template support
- VXLAN definition improvements (dhcp relay, mtu)

Version 0.2.0
-------------

New features:

- Syncto for dist devices
- VXLAN definitions in settings
- Firmware upgrade for Arista

Version 0.1.0
-------------

Initial test release including device database, syncto and ZTP for access devices, git repository refresh etc.
