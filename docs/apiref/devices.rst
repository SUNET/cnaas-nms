Devices
=======

The API is used to manage devices, interfaces and other objects used by the CNaaS NMS. All requests in the examples belove are using 'curl'.

Show devices
------------

To list all devices the following REST call can be done:

::

   curl https://hostname/api/v1.0/device

However, is a single device should be filtered out, the device name
can be send as part of the URL:

::

   curl https://hostname/api/v1.0/device/ex2300-top

Add devices
-----------

A single device can be added by sending a REST call with a JSON
strcuture describing the device as data. The JSON strcuture should
have the following format:

::

   * hostname (mandatory)
   * site_id (optional)
   * site (optional)
   * description (optional)
   * management_ip (optional)
   * dhcp_ip (optional)
   * serial (optional)
   * ztp_mac (optional)
   * platform (optional)
   * vendor (optional)
   * model (optional)
   * os_version (optional)
   * synchronized (optional)
   * state (mandatory)
   * device_type (mandatory)

There are three mandatory fields that can not be left out: hostname,
state and device_type.

Device state can be one of the following:

::

   UNKNOWN:         Unhandled programming error
   PRE_CONFIGURED:  Pre-populated, not seen yet
   DHCP_BOOT:       Something booted via DHCP, unknown device
   DISCOVERED:      Something booted with base config, temp ssh access for conf push
   INIT:            Moving to management VLAN, applying base template
   MANAGED:         Correct managament and accessible via conf push
   MANAGED_NOIF:    Only base system template managed, no interfaces?
   UNMANAGED:       Device no longer maintained by conf push

The mandatory field device_type can be:

::

   * UNKNOWN
   * ACCESS
   * DIST
   * CORE

Example CURL call:

::

   curl --header "Content-Type: application/json" -X POST --data
   '"hostname":"foo","state":"UNKNOWN","device_type":"UNKNOWN"'
   https://hostname/api/v1.0/device

Modify devices
--------------

An existing device can be modified, in that case the devices ID should
be appended to the URL. The URL will then have the following format:

::

   https://hostname/api/v1.0/device/10

Where 10 is the device ID.

To modify a device, use the same JSON data as for adding new devices:

::

   curl --header "Content-Type: application/json" -X PUT --data
   "state":"UNKNOWN","device_type":"DIST"'
   https://hostname/api/v1.0/device/10


Remove devices
--------------

To remove a device, pass the device ID in a DELTE call:

::

   curl -X PUT https://hostname/api/v1.0/device/10
