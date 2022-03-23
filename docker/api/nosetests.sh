#!/bin/bash

cd /opt/cnaas
source venv/bin/activate

cd venv/cnaas-nms/src

export USERNAME_DHCP_BOOT="admin"
export PASSWORD_DHCP_BOOT="abc123abc123"
export USERNAME_DISCOVERED="admin"
export PASSWORD_DISCOVERED="abc123abc123"
export USERNAME_INIT="admin"
export PASSWORD_INIT="abc123abc123"
export USERNAME_MANAGED="admin"
export PASSWORD_MANAGED="abc123abc123"

# Don't run unittests that requires live equipment if NO_EQUIPMENTTEST is set
if [ -z "$NO_EQUIPMENTTEST" ] ; then
	export NOSE_TESTMATCH="(?:^|[\b_\./-])(equipment)?[Tt]est"
fi

if [ -z "$COVERAGE" ] ; then
	nosetests -v
	EXITSTATUS=$?
else
	nosetests --collect-only --with-id -v
	nosetests --with-coverage --cover-package=cnaas_nms -v
	EXITSTATUS=$?
	cp .coverage /coverage/.coverage-nosetests
fi

exit $EXITSTATUS
