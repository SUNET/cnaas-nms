Management domains
==================

Management domain can be retreived, added, updated an removed using this API.

Get all managment domains
-------------------------

All management domain can be listed using CURL:


::

   curl -s -H "Authorization: Bearer $JWT_AUTH_TOKEN" ${CNAASURL}/api/v1.0/mgmtdomains

That will return a JSON structured response which describes all domains available:

::

  {
      "status": "success",
      "data": {
          "mgmtdomains": [
              {
                  "id": 10,
                  "ipv4_gw": "10.0.6.1/24",
                  "device_a_id": 9,
                  "device_a_ip": null,
                  "device_b_id": 12,
                  "device_b_ip": null,
                  "site_id": null,
                  "vlan": 600,
                  "description": null,
                  "esi_mac": null,
                  "device_a": "eosdist",
                  "device_b": "eosdist2"
              }
          ]
      }
  }

You can also specify one specifc mgmtdomain to query by using:

::

   curl -s -H "Authorization: Bearer $JWT_AUTH_TOKEN" ${CNAASURL}/api/v1.0/mgmtdomain/10



Add management domain
---------------------

To add a new management domain we can to call the API with a few fields set in a JSON structure:

::

   * ipv4_gw (mandatory): The IPv4 gateway to be used, should be expressed with a prefix (10.0.0.1/24)
   * device_a (mandatory): Hostname of the first device
   * device_b (mandatory): Hostname of the second device
   * vlan (mandatory): A VLAN

Example using CURL:

::

   curl -s -H "Authorization: Bearer $JWT_AUTH_TOKEN" ${CNAASURL}/api/v1.0/mgmtdomain -H "Content-Type: application/json" -X POST -d '{"ipv4_gw": "10.0.6.1/24", "device_a": "dist1", "device_b": "dist2", "vlan": 600}'


Update management domain
------------------------

To update a doamin, we can send a PUT request and specify its ID. We will have to send the same JSON structure as when adding a new domain:

::

   curl -s -H "Authorization: Bearer $JWT_AUTH_TOKEN" ${CNAASURL}/api/v1.0/mgmtdomain/4 -H "Content-Type: application/json" -X PUT -d '{"ipv4_gw": "10.0.6.1/24", "device_a": "dist1", "device_b": "dist2", "vlan": 600}'


Remove management domain
------------------------

We can also remove an existing domain by sending a DELETE request and specify its ID:

Once again using CURL:

::

   curl -s -H "Authorization: Bearer $JWT_AUTH_TOKEN" ${CNAASURL}/api/v1.0/mgmtdomain/4 -X DELETE
