Management domains
==================

Management domain can be retreived, added, updated an removed using this API.

Get all managment domains
-------------------------

All management domain can be listed using CURL:


::

   curl -X GET http://hostname/api/v1.0/mgmtdomain

That will return a JSON structured response which describes all domains available:

::

   {
    "status": "success",
    "data": {
	"mgmtdomains": [
	    {
		"id": 4,
		"ipv4_gw": "192.168.50.0/24",
		"device_a_id": 9,
		"device_a_ip": null,
		"device_b_id": 12,
		"device_b_ip": null,
		"site_id": null,
		"vlan": 600,
		"description": null
	    }
	]
      }
   }


We can also retreive a specific domain by specifying its ID:

::

   curl -X GET http://hostname/api/v1.0/mgmtdomain

   {
    "status": "success",
    "data": {
	"mgmtdomains": [
	    {
		"id": 4,
		"ipv4_gw": "192.168.50.0/24",
		"device_a_id": 9,
		"device_a_ip": null,
		"device_b_id": 12,
		"device_b_ip": null,
		"site_id": null,
		"vlan": 600,
		"description": null
	    }
	]
     }
   }


Add management domain
---------------------

To add a new management domain we can to call the API with a few fields set in a JSON structure:

::

   * ipv4_gw (mandatory): The IPv4 gateway to be used, should be expressed with a prefix
   * device_a (mandatory): ID of the first device
   * device_b (mandatory): ID of the second device
   * vlan (mandatory): A VLAN

Example using CURL:

::

   curl -H "Content-Type: application/json" -X POST http://localhost:5000/api/v1.0/mgmtdomain -d '{"ipv4_gw": "1.2.3.4/32", "device_a": 9, "device_b": 12, "vlan": 100}'


Update management domain
------------------------

To update a doamin, we can send a PUT request and specify its ID. We will have to send the same JSON structure as when adding a new domain:

::

   curl -H "Content-Type: application/json" -X PUT http://localhost:5000/api/v1.0/mgmtdomain/4 -d '{"ipv4_gw": "1.2.3.4/32", "device_a": 9, "device_b": 12, "vlan": 100}'


Remove management domain
------------------------

We can also remove an existing domain by sending a DELETE request and specify its ID:

Once again using CURL:

::

   curl -X DELETE http://hostname/api/v1.0/mgmtdomain/4
