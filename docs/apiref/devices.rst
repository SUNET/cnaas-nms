Devices
=======

The API is used to manage devices, interfaces and other objects used by the CNaaS NMS. All requests in the examples belove are using 'curl'.

Show devices
------------

A single device entry can be listed by device_id:

::

   curl https://hostname/api/v1.0/device/9

This will return the entire device entry from the database:

::

  {
      "status": "success",
      "data": {
          "devices": [
              {
                  "id": 9,
                  "hostname": "eosdist",
                  "site_id": null,
                  "description": null,
                  "management_ip": "10.100.3.101",
                  "dhcp_ip": null,
                  "infra_ip": null,
                  "oob_ip": null,
                  "serial": null,
                  "ztp_mac": "08002708a8be",
                  "platform": "eos",
                  "vendor": null,
                  "model": null,
                  "os_version": null,
                  "synchronized": true,
                  "state": "MANAGED",
                  "device_type": "DIST",
                  "confhash": null,
                  "last_seen": "2019-02-27 10:30:23.338681",
                  "port": null
              }
          ]
      }
  }


To list all devices the following API call can be used:

::

   curl https://hostname/api/v1.0/devices

You can also do filtering, ordering and limiting of results from the devices API:

::

   curl "https://hostname/api/v1.0/devices?filter[hostname][contains]=eos&filter[device.type]=dist&page=2&per_page=50&sort=-hostname"

This will filter the results like so:

* Only devices that has a hostname that contains the string "eos" will be returned
* Only devices that has type exactly matching "dist" will be returned
* A maximum of 50 results will be returned (per_page=50)
* The second page of results will be returned, since per_page is set to 50 this means items 51-100 (page=2)
* The results will be ordered based on the column hostname, in descending order. "-" means descending, no prefix means ascending (sort=-hostname)

A HTTP header with the name X-Total-Count will show the unfiltered total number of devices in the database.


Add devices
-----------

A single device can be added by sending a REST call with a JSON
strcuture describing the device as data. The JSON strcuture should
have the following format:

   * hostname (mandatory)
   * site_id (optional)
   * site (optional)
   * description (optional)
   * management_ip (optional)
   * infra_ip (optional)
   * dhcp_ip (optional)
   * serial (optional)
   * ztp_mac (optional)
   * platform (mandatory)
   * vendor (optional)
   * model (optional)
   * os_version (optional)
   * synchronized (optional)
   * state (mandatory)
   * device_type (mandatory)

There are four mandatory fields that can not be left out: hostname,
state, platform and device_type.

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

   * UNKNOWN
   * ACCESS
   * DIST
   * CORE

If you specify a device_type of CORE or DIST but do not specify management_ip
or infra_ip these will be selected automatically from the next available IP
from the network specified in the settings repository.

Example CURL call:

::

   curl -H "Content-Type: application/json" -X POST -d
   '{"hostname":"foo", "state":"UNKNOWN", "device_type":"DIST", "platform": "eos"}'
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

   curl -X DELETE https://hostname/api/v1.0/device/10


Preview config
--------------

To preview what config would be generated for a device without actually
touching the device use generate_config:

::

  curl https://hostname/api/v1.0/device/<device_hostname>/generate_config

This will return both the generated configuration based on the template for
this device type, and also a list of available vaiables that could be used
in the template.
