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

nosetests --collect-only --with-id -v
nosetests --with-coverage --cover-package=cnaas_nms -v
cp .coverage /coverage/.coverage-nosetests

