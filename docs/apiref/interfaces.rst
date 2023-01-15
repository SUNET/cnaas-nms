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

   curl https://hostname/api/v1.0/device/eosaccess/interfaces

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
- CUSTOM: Use custom configuration defined in settings YAML (only implemented for DIST type devices)
- TEMPLATE: Use a pre-defined template (not implemented)
- ACCESS_AUTO: Use 802.1X configuration to automatically configure port (default)
- ACCESS_UNTAGGED: Use a static VLAN defined by name in the data field
- ACCESS_TAGGED: Use a static list of VLANs defined by names in the data field
- ACCESS_UPLINK: Uplink from access switch to dist switch
- ACCESS_DOWNLINK: Downlink from this access switch to another access switch
- MLAG_PEER: MLAG peer interface

Update interface
----------------

Set device eosaccess to use statically configured untagged VLAN with name "STUDENT" on interface Ethernet1

::

   curl https://hostname/api/v1.0/device/eosaccess/interfaces -d '{"interfaces": {"Ethernet1": {"configtype": "access_untagged", "data": {"untagged_vlan": "STUDENT"}}}}' -X PUT -H "Content-Type: application/json"

Response:

::

  {
      "status": "success",
      "data": {
          "updated": {
              "Ethernet1": {
                  "configtype": "ACCESS_UNTAGGED",
                  "data": {
                      "untagged_vlan": "STUDENT"
                  }
              }
          }
      }
  }

To change the port back to the default ACCESS_AUTO port type use:

::

  curl https://hostname/api/v1.0/device/eosaccess/interfaces -d '{"interfaces": {"Ethernet1": {"configtype": "access_auto"}}}' -X PUT -H "Content-Type: application/json"

Response:

::

  {
      "status": "success",
      "data": {
          "updated": {
              "Ethernet1": {
                  "configtype": "ACCESS_AUTO"
              }
          }
      }
  }


If you want to specify a statically configured port with tagged VLANs (trunk port) use an API call like this:

::

  curl https://hostname/api/v1.0/device/eosaccess/interfaces -d '{"interfaces": {"Ethernet1": {"configtype": "access_tagged", "data": {"tagged_vlan_list": ["STUDENTT"]}}}}' -X PUT -H "Content-Type: application/json" -H "Authorization: Bearer $JWT_AUTH_TOKEN"

Response:

::

  {
      "status": "error",
      "message": {
          "errors": [
              "Some VLAN names STUDENTT are not present in eosaccess"
          ],
          "updated": {
              "Ethernet1": {
                  "configtype": "ACCESS_TAGGED"
              }
          }
      }
  }


In this case the configtype was updated but one of the names in the VLAN list
was not present on this switch and therefore the VLAN list was not updated.
You can check what VLAN names exist on a specific switch by using the /settings
API call and specifying the hostname and then look for the vlan_name field
under a specific vxlan.

Data can contain any of these optional keys:

- untagged_vlan: Numeric or string representation of a VLAN/VXLAN from vxlans.yml
- tagged_vlan_list: List of VLANs/VXLANs
- description: Description for the interface, this should be a string 0-64 characters.
- enabled: Set the administrative state of the interface. Defaults to true if not set.
- aggregate_id: Identifier for configuring LACP etc. Integer value.
  Special value -1 means configure MLAG and use ID based on indexnum.
- bpdu_filter: bool defining STP BPDU feature enabled/disabled
- redundant_link: bool allows specifying if this link allows non-redundant downlinks
- tags: List of strings, user-defined custom tags to use in templates
- cli_append_str: String of custom config that is appended to generated CLI config
- neighbor: Populated at init, contains hostname of peer. Should normally never
  have to be updated via API.
- neighbor_id: Populated at init, contains device id of peer. Should normally never
  have to be updated via API.

Setting an optional value to JSON null will remove it from the database.

To disable a port:

::

  curl https://hostname/api/v1.0/device/eosaccess/interfaces -d '{"interfaces": {"Ethernet1": {"data": {"enabled": false, "description": "Disabled becasue of abuse 2020-01-30 by kosmoskatten"}}}}' -X PUT -H "Content-Type: application/json" -H "Authorization: Bearer $JWT_AUTH_TOKEN"

To re-enable and unset description:

::

  curl https://hostname/api/v1.0/device/eosaccess/interfaces -d '{"interfaces": {"Ethernet1": {"data": {"enabled": true, "description": null}}}}' -X PUT -H "Content-Type: application/json" -H "Authorization: Bearer $JWT_AUTH_TOKEN"

If the list of interfaces does not match what currently exists on the device
you need to run the device_update_interfaces API call (see device API).

Show interface states
---------------------

To get the currently active state of interfaces on a device like admin state (is_up) etc, use:

::

   curl https://hostname/api/v1.0/device/eosaccess/interface_status

Response:

::

   {
       "status": "success",
       "data": {
           "interface_status": {
               "Management1": {
                   "is_up": true,
                   "is_enabled": true,
                   "description": "",
                   "last_flapped": 1581950162.341227,
                   "speed": 1000,
                   "mac_address": "08:00:27:F5:D6:58"
               }
           }
       }
   }

Bounce interfaces
-----------------

If you want to quickly disale and then re-enable an interface to reboot a PoE
connected access point for example, you can use the "bounce interfaces" API.
Send a list of interfaces to the specified device like this:

::

  curl https://hostname/api/v1.0/device/eosaccess/interface_status -d '{"bounce_interfaces": ["Ethernet1"]}' -X PUT -H "Content-Type: application/json" -H "Authorization: Bearer $JWT_AUTH_TOKEN"

Response:

::

   {
       "status": "success",
       "data": "Bounced interfaces: Ethernet1"
   }


You can only bounce non-uplink interfaces of ACCESS type switches. This is to prevent
accidentally losing connectivity to the device.
