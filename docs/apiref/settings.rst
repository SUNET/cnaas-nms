Settings
========

This API can be used to retreveive all settings defied in the settings repository.

We can sort settings per hostname or device type.

To get all settings:

::

   curl -X GET http://hostname/api/v1.0/settings

This will return all settings for all devices:

::

   {
    "status": "success",
    "data": {
        "settings": {
            "ntp_servers": [
                {
                    "host": "194.58.202.148"
                },
                {
                    "host": "256.256.256.256"
                }
            ],
            "radius_servers": [
                {
                    "host": "10.100.2.3"
                }
            ],
            "syslog_servers": null
        },
        "settings_origin": {
            "ntp_servers": "device",
            "radius_servers": "devicetype",
            "groups": "global"
        }
      }
   }

We can also chose to only get settings for a specific hostname:

::

   curl -X GET http://hostname/api/v1.0/settings?hostname=eosaccess

Or by a specific type of devices:

::

   curl -X GET http://hostname/api/v1.0/settings?device_type=access
