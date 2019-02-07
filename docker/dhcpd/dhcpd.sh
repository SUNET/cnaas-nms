#!/bin/bash

set -e

touch /var/lib/dhcp/dhcpd.leases

/usr/sbin/dhcpd -4 -f -d --no-pid -cf /opt/cnaas/dhcpd.conf
