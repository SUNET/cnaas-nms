#!/bin/bash

set -e

if [ ! -z "$GITREPO_ETC" ]
then
	cd /opt/cnaas
	rm -rf /opt/cnaas/etc
        base_url=$(echo $GITREPO_ETC | cut -d\# -f1)
        branch=$(echo $GITREPO_ETC | cut -d\# -s -f2)
        if [ -n "$branch" ]; then
           branch="-b $branch"
        fi
	git clone $branch $base_url etc
	if [ -f "/opt/cnaas/etc/dhcpd/dhcpd.conf" ]
	then
		cp /opt/cnaas/etc/dhcpd/dhcpd.conf /opt/cnaas/dhcpd.conf
	fi
fi

if [ -e "/opt/cnaas/etc/dhcpd/gen-dhcpd.py" ] && \
       [ -e "/opt/cnaas/etc/dhcpd/dhcpd.j2" ] && \
       [ -e "/opt/cnaas/etc/dhcpd/dhcpd.yaml" ]; then
    source /opt/cnaas/venv/bin/activate
    cd /opt/cnaas/etc/dhcpd/
    python3 gen-dhcpd.py > /opt/cnaas/dhcpd.conf
fi

#cd /opt/cnaas/venv/cnaas-nms
#git pull

touch /var/lib/dhcp/dhcpd.leases

sleep 10

/usr/sbin/dhcpd -4 -f -d --no-pid -cf /opt/cnaas/dhcpd.conf
