Devices
=======

The API is used to manage devices, interfaces and other objects used by the CNaaS NMS. All requests in the examples belove are using 'curl'.

Show devices
------------

To list all devices the following REST call can be done:

::
   
   curl http://10.0.1.5:5000/api/v1.0/device

However, is a single device should be filtered out, the device name
can be send as part of the URL:

::
   
   curl http://10.0.1.5:5000/api/v1.0/device/ex2300-top
   
Add devices
-----------

A single device can be added by sending a REST call with a JSON
strcuture describing the device as data. The JSON strcuture should
have the following format:

::

   hostname (mandatory), the hostname of the device to be added
   site_id (optional),
   site (optional),
   description (optional),
   management_ip (optional),
   dhcp_ip (optional),
   serial (optional),
   ztp_mac (optional),
   platform (optional),
   vendor (optional),
   model (optional),
   os_version (optional),
   synchronized (optional),
   state (mandatory)
   device_type (mandatory)


Modify devices
--------------

Remove devices
--------------
