Settings
========

This API can be used to retreveive all settings defied in the settings repository.

We can sort settings per hostname or device type.

To get all settings:

::

   curl https://hostname/api/v1.0/settings

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

   curl https://hostname/api/v1.0/settings?hostname=eosaccess

Or by a specific type of devices:

::

   curl https://hostname/api/v1.0/settings?device_type=access

Settings model
--------------

You can also retrieve the model used by the currently running version of
CNaaS-NMS to verify the settings. This might help you understand why certain
settings are not considered valid.

Example:

::

   curl https://hostname/api/v1.0/settings/model

$ref fields mean that the definition of this "field" is set somewhere else
in this output. Look under the "definitions" part. Patterns are Python
regular expressions.

You can also test out specific settings by sending them to the API with a
POST call like this:

::

   curl https://hostname/api/v1.0/settings/model -X POST -d '{"radius_servers": [{"host": "1.1.1.1"}]}' -H "Content-Type: application/json"

Example with invalid IP/hostname:

::

   curl https://hostname/api/v1.0/settings/model -X POST -d '{"radius_servers": [{"host": "10.0.0.500"}]}' -H "Content-Type: application/json"

Output:

::

   {
     "status": "error",
     "message": "Validation error for setting radius_servers->0->host, bad value: 10.0.0.500 (value origin: API POST data)\nMessage: string does not match regex \"^((?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)|([a-z0-9-]{1,63}\\.)([a-z-][a-z0-9-]{1,62}\\.?)+)$\", field should be: Hostname, FQDN or IP address\n"
   }
