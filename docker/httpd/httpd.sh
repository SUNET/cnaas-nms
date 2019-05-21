#!/bin/bash

if [ -z "$GITREPO" ]
then
	cd /opt/cnaas/www
	rm -rf /opt/cnaas/www/templates
	git clone "$GITREPO" templates
else
	cd /opt/cnaas/www/templates
	git pull
fi

set -e

nginx -c /opt/cnaas/nginx.conf -g "daemon off;"
