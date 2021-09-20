Changelog
=========

Version 1.3.0
-------------

New features:

 - CNaaS specific Jinja2 filters: increment_ip, ipv4_to_ipv6, isofy_ipv4 (#167)
 - "aggregate_id" option for access ports to build link aggregates from access switches (#171)
 - New settings for: flow_collectors, route leaking, port_template, dot1x_fail_vlan, vxlan tags (#178,#192,#193,#194,#195,#196)
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
