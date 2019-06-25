#!/bin/bash

if [ -z "$GITREPO_TEMPLATES" ]
then
	cd /opt/cnaas/www/templates
	git pull
else
	cd /opt/cnaas/www
	rm -rf /opt/cnaas/www/templates
	git clone $GITREPO_TEMPLATES templates
fi

set -e

nginx -c /opt/cnaas/nginx.conf -g "daemon off;"
