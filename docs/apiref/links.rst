Links
=====

This API is used to retreive information about which access switch is
connected to which distribution switches. Normally one access switch
is connected to two distribution switches on two separate uplinks.

For example Ethernet1 on the access switch might be connected to
Ethernet1 on the dist switch, and Ethernet2 connected to Ethernet2.

Show links
----------

It is only possible to fetch information about links using the API.

This can be done using CURL:


::

   curl http://hostname/api/v1.0/linknet

The result will look like this:

::

    {
        "status": "success",
        "data": {
            "linknet": [
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

    curl -ks -H "Authorization: Bearer $JWT_AUTH_TOKEN" ${CNAASURL}/api/v1.0/linknets -X POST -d '{"device_a": "eosdist", "device_a_port": "Ethernet3", "device_b": "eosdist2", "device_b_port": "Ethernet3"}' -H "Content-Type: application/json"

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
