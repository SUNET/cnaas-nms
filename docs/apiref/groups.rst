Groups
======

This API is used to list groups. Groups are configured in the settings
and can be defined to include one or more devices.

Show groups
-----------

To show all groups the following REST call can be used:

::

   curl https://hostname/api/v1.0/groups

That will return a JSON structure with all group names
and the hostnames of all devices in the group:

::

   {
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

Show specific group
-------------------

To show a specific group specify the group name in the path:

::

   curl https://hostname/api/v1.0/groups/mygroup


Define groups
-------------

New groups can be defined in the settings repository.

