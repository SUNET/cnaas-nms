Groups
======

This API is used to list groups. Groups are configured in the settings
and can be defined to include one or more devices.

Show groups
-----------

To show all groups the following REST call can be used:

::

   curl https://hostname/api/v1.0/groups

That will return a JSON structure with all the groups defined:

::

   {
     "status": "success",
     "data": {
        "status": "success",
        "data": {
            "groups": {
                "group_0": [
                    "testdevice_a",
                ],
                "group_1": [
                    "testdevice_b",
		    "testdevice_c"
                ]
            }
         }
      }
   }


Define groups
-------------

New groups can be defined in the settings template.

In the global settings, modify 'base_system.yml' and add the following
section:

::
   
   groups:
   - group:
      name: 'MY_NEW_GROUP'
      regex: '.*'
   - group:
      name: 'ANOTHER_NEW_GROUP'
      regex: '.*'

As you can see, a name and a regex is expected. The regex will match
on the device hostnames and based on that add them to the group.
