Plugins
=======

CNaaS-NMS uses an extendable and configurable plugin system that can be used to integrate
external systems into certain workflows. Plugins register to predefined hooks in the CNaaS-NMS
system and gets called with a set of arguments specific to that hook. Multiple plugins can
register for the same hooks at the same time.
For example, when a new device is added to CNaaS all plugins with the hook new_managed_device
will be called with arguments like hostname and device type.

Configuration
-------------

/etc/cnaas-nms/plugins.yml configuration example::

  ---
  plugins:
    - filename: filewriter.py
      vars:
        logfile: "/tmp/filewriter.log"

This file contains a list of plugins that should be loaded.
Any vars defined here can be accessed from the plugin, this can be used to set
URLs to other system APIs etc.

What plugins got loaded and what variables that are available can be accessed via the
rest API as well.

Hooks
-----

new_managed_device
^^^^^^^^^^^^^^^^^^

Called when a new device is initialized through the init_device API call and that device
reaches the "MANAGED" state.

Arguments provided:

- hostname: Hostname of the new device
- device_type: What type of device, ACCESS, DIST or CORE
- serial_number: Serial number of device
- vendor: Vendor/manufacturer of device
- model: Hardware model of device
- os_version: Operating System version of device

allocated_ipv4
^^^^^^^^^^^^^^

Called when CNaaS-NMS has allocated a new IPv4 address and configured it on a device.
Currently only called during the init_device API call.

Argumens proided:

- vrf: Name of the VRF used (ex mgmt)
- ipv4_address: IPv4 address (ex 10.0.6.6)
- ipv4_network: IPv4 network address in CIDR notation (ex 10.0.6.0/24)
- hostname: Hostname of the device that uses this address

