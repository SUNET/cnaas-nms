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

To show a single group specify the group name in the path:

::

   curl https://hostname/api/v1.0/groups/mygroup


Show specific group OS versions
-------------------------------

To show the OS versions of the devices in a group:

::

   curl https://hostname/api/v1.0/groups/MY_EOS_DEVICES/os_versions

Output:

::

   {
       "status": "success",
       "data": {
           "groups": {
               "MY_EOS_DEVICES": {
                   "4.21.1.1F-10146868.42111F": [
                       "eosaccess"
                   ],
                   "4.22.3M-14418192.4223M": [
                       "eosdist1",
                       "eosdist2"
                   ]
               }
           }
       }
   }



Define groups
-------------

New groups can be defined in the settings repository. :ref:`settings_repo_ref`

