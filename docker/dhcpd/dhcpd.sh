#!/bin/bash

set -e

sed -e "s/^\(password: \).\+$/\1 $DB_PASSWORD/" \
    -e "s/^\(hostname: \).\+$/\1 $DB_HOSTNAME/" \
    -e "s/^\(mongo_hostname: \).\+$/\1 $MONGODB_HOSTNAME/" \
  < /etc/cnaas-nms/db_config.yml > db_config.yml.new \
  && mv -f db_config.yml.new /etc/cnaas-nms/db_config.yml

if [ ! -z "$GITREPO_ETC" ]
then
	cd /opt/cnaas
	rm -rf /opt/cnaas/etc
	git clone $GITREPO_ETC etc
	if [ -f "/opt/cnaas/etc/dhcpd/dhcpd.conf" ]
	then
		cp /opt/cnaas/etc/dhcpd/dhcpd.conf /opt/cnaas/dhcpd.conf
	fi
fi

#cd /opt/cnaas/venv/cnaas-nms
#git pull

touch /var/lib/dhcp/dhcpd.leases

sleep 10

/usr/sbin/dhcpd -4 -f -d --no-pid -cf /opt/cnaas/dhcpd.conf
