Changelog
=========

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
