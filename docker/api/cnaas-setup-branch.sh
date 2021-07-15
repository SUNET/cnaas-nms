#!/bin/bash

set -e
set -x

# Temporary for testing new branch
if [ "$1" != "develop" ] ; then
	cd /opt/cnaas/venv/cnaas-nms/
	git fetch --all
	git checkout --track origin/$1
	source /opt/cnaas/venv/bin/activate
	python3 -m pip install -r requirements.txt
fi
