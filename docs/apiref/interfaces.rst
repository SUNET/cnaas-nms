Interfaces
==========

This API is used to query and update information about physical
interfaces on access switches managed by CNaaS-NMS.
Interfaces for dist and core devices are managed through YAML
files in the git repositories.

Show interfaces
---------------

List all interfaces on device eosaccess

::

   curl http://hostname/api/v1.0/interfaces/eosaccess

The result will look something like this:

::

  {
      "status": "success",
      "data": {
          "interfaces": [
              {
                  "device_id": 13,
                  "name": "Ethernet3",
                  "configtype": "ACCESS_UPLINK",
                  "data": null
              },
              {
                  "device_id": 13,
                  "name": "Ethernet2",
                  "configtype": "ACCESS_UPLINK",
                  "data": null
              },
              {
                  "device_id": 13,
                  "name": "Ethernet1",
                  "configtype": "ACCESS_AUTO",
                  "data": null
              }
          ],
          "hostname": "eosaccess"
      }
  }

The configtype field must use some of these pre-defined values:

- UNKNOWN: Should not be used unless there's an error in CNaaS-NMS
- UNMANAGED: This interface is not managed by CNaaS-NMS (not implemented)
- CONFIGFILE: This interface is managed via external config file (not implemented)
- CUSTOM: Use custom configuration from data field (not implemented)
- TEMPLATE: Use a pre-defined template (not implemented)
- ACCESS_AUTO: Use 802.1X configuration to automatically configure port (default)
- ACCESS_UNTAGGED: Use a static VXLAN defined in data field
- ACCESS_TAGGED: Use a static list of VXLANs defined in data field (not implemented)
- ACCESS_UPLINK: Uplink from access switch to dist switch

Update interface
----------------

Set Ethernet1 to use statically configured VXLAN called student1

::

   curl http://hostname/api/v1.0/interfaces/eosaccess -d '{"interfaces": {"Ethernet1": {"data": {"vxlan": "student1"}}}}' -X PUT -H "Content-Type: application/json"

Response:

::

  {
      "status": "success",
      "data": {
          "updated": {
              "Ethernet1": {
                  "data": {
                      "vxlan": "student1"
                  }
              }
          }
      }
  }

You should also update the configtype of the interface to make
use of the specified VXLAN:

::

  curl http://hostname/api/v1.0/device/eosaccess/interfaces -d '{"interfaces": {"Ethernet1": {"configtype": "access_untagged", "data": {"vxlan": "student123"}}}}' -X PUT -H "Content-Type: application/json"

If you specify a VXLAN that is not available in this switch you
will get an error message like this:

::

  {
      "status": "error",
      "message": {
          "errors": [
              "Specified VXLAN student123 is not present in eosaccess"
          ],
          "updated": {
              "Ethernet1": {
                  "configtype": "ACCESS_UNTAGGED"
              }
          }
      }
  }

In this case the configtype was updated but the VXLAN was not
updated since it was not available in this switch.