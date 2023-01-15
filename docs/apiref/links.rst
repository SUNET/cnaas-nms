Linknets
========

This API is used to retreive and modify information about links between
devices. Links between access switches and distribution switches are normally
Layer2 ports and thus have no IP information, while links between dist and
core devices are Layer3 ports and have information about IP addressing.

An access switch normally has two uplink ports connected to two different
distribution switches like in the example below.

Show linknets
-------------

To get information about existing links in the database, use a GET query to
api/v1.0/linknets

This can be done using CURL:

::

   curl -s -H "Authorization: Bearer $JWT_AUTH_TOKEN" ${CNAASURL}/api/v1.0/linknets

The result will look like this:

::

    {
        "status": "success",
        "data": {
            "linknets": [
                {
                    "id": 8,
                    "ipv4_network": null,
                    "device_a_id": 13,
                    "device_a_ip": null,
                    "device_a_port": "Ethernet1",
                    "device_b_id": 9,
                    "device_b_ip": null,
                    "device_b_port": "Ethernet1",
                    "site_id": null,
                    "description": null
                },
                {
                    "id": 10,
                    "ipv4_network": null,
                    "device_a_id": 13,
                    "device_a_ip": null,
                    "device_a_port": "Ethernet2",
                    "device_b_id": 12,
                    "device_b_ip": null,
                    "device_b_port": "Ethernet2",
                    "site_id": null,
                    "description": null
                }
            ]
        }
    }

In the result above device_a is the access switch and device_b is the
dist switch.

You can also specify one specifc link to query by using:

::

   curl -s -H "Authorization: Bearer $JWT_AUTH_TOKEN" ${CNAASURL}/api/v1.0/linknet/10

Manually provision a new linknet
--------------------------------

When adding switches manually instead of using ZTP you might also need to
manually create linknets.

Example:

::

    curl -s -H "Authorization: Bearer $JWT_AUTH_TOKEN" ${CNAASURL}/api/v1.0/linknets -X POST -d '{"device_a": "eosdist", "device_a_port": "Ethernet3", "device_b": "eosdist2", "device_b_port": "Ethernet3"}' -H "Content-Type: application/json"

Output:

::

    {
        "status": "success",
        "data": {
            "id": 25,
            "ipv4_network": "10.198.0.0/31",
            "device_a_id": 9,
            "device_a_ip": "10.198.0.0",
            "device_a_port": "Ethernet3",
            "device_b_id": 12,
            "device_b_ip": "10.198.0.1",
            "device_b_port": "Ethernet3",
            "site_id": null,
            "description": null
        }
    }

A new IP subnet is automatically allocated as the next free /31 from the
settings variable underlay->infra_link_net

It's also possible to specify a linknet manually with the "ipv4_network"
argument but it has to be a /31 network.

Update linknet
--------------

To update a linknet, we can send a PUT request and specify its ID. You can
update the fields "ipv4_network" (must be /31 to /29), "device_a_port",
"device_b_port", "device_a_ip", "device_b_ip" (both must be within ipv4_network)

::

   curl -s -H "Authorization: Bearer $JWT_AUTH_TOKEN" ${CNAASURL}/api/v1.0/linknet/4 -H "Content-Type: application/json" -X PUT -d '{"device_b_port": "Ethernet3"}'


Manually deleting a linknet
---------------------------

To delete a linknet from use the DELETE method. Use this carefully
since it might affect reachability!

Example:

::

  curl -s -H "Authorization: Bearer $JWT_AUTH_TOKEN" ${CNAASURL}/api/v1.0/linknet/<id> -X DELETE
