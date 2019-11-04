Links
=====

This API is used to retreive and modify information about links between
devices. Links between access switches and distribution switches are normally
Layer2 ports and thus have no IP information, while links between dist and
core devices are Layer3 ports and have information about IP addressing.

An access switch normally has two uplink ports connected to two different
distribution switches like in the example below.

Show links
----------

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

Manually provision a new link
-----------------------------

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

Manually deleting a link
------------------------

If you made some error while manually adding a link you can delete it and
recreate it. Use this carefully since it might affect reachability for
the entire fabric.

Example:

::

  curl -s -H "Authorization: Bearer $JWT_AUTH_TOKEN" ${CNAASURL}/api/v1.0/linknets -X DELETE -d '{"id": 25}' -H "Content-Type: application/json"
