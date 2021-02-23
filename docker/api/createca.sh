#!/bin/bash

if [ -f /opt/cnaas/cacert/rootCA.key ] || [ -f /opt/cnaas/cacert/rootCA.crt ]
then
	exit 0
fi

cd /opt/cnaas/cacert
umask 077
openssl genrsa -out rootCA.key 4096
openssl req -subj /C=/ST=/L=/O=/CN=cnaasNMSrootCA -x509 -new -nodes -key rootCA.key -sha256 -out rootCA.crt -days 7300
chown root:www-data rootCA.*
chmod 640 rootCA.*

