System
======

Version
-------

To get the currently running version of the CNaaS-NMS API:

::

   curl https://hostname/api/v1.0/system/version

Example output:

::

   {
       "status": "success",
       "data": {
           "version": "0.2.0.dev0",
           "git_version": "Git commit 3a08c0e10d1cc31a4634d383e12394e758615747 feature.settings_dhcprelay (2020-01-20 13:07:48+01:00)"
       }
   }
