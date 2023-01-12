Changelog
=========

Version 1.4.0
-------------

New features:

 - Support interface range expressions like Ethernet[10-11] in settings device interface config
 - Save last know working settings commit, so we can revert if last commit contains errors
   (only saved in memory, not persistent across reboots)
 - Allow sync of devices with multiple links between same peers.
 - Allow updating of neighbor_id on interface (useful if manually changing uplink connections)
 - New settings: organization_name, domain_name, underlay->bgp_asn
 - New jinja filters: different base-encodings, hashes, netutils for IP, MAC, ASNs etc
 - New global config settings:
  * global_unique_vlans: If True VLAN IDs has to be globally unique, if False
    different DIST switches can reuse same VLAN IDs for different L2 domains.
    Defaults to True.
  * init_mgmt_timeout: Timeout to wait for device to apply changed management IP.
    Defaults to 30, specified in seconds (integer).

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

New settings:

    New settings for vxlans: acl_ipv4_in, acl_ipv4_out, acl_ipv6_in, acl_ipv6_out, cli_append_str
    New data options in interfaces API: bpdu_filter, tags, cli_append_str

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
