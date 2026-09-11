Health
======

Version
-------

To get the current health status:

::

   curl https://hostname/api/health

Example output:

::

   {
       "status": "success",
       "checks": {
           "postgres": "healthy",
           "redis": "healthy"
       }
   }
