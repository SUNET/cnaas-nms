#!/bin/bash

set -e

sed -e "s/^\(password: \).\+$/\1 $DB_PASSWORD/" \
    -e "s/^\(hostname: \).\+$/\1 $DB_HOSTNAME/" \
  < /etc/cnaas-nms/db_config.yml > db_config.yml.new \
  && mv -f db_config.yml.new /etc/cnaas-nms/db_config.yml

touch /var/lib/dhcp/dhcpd.leases

/usr/sbin/dhcpd -4 -f -d --no-pid -cf /opt/cnaas/dhcpd.conf
