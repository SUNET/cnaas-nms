#!/bin/bash

cd /opt/cnaas
source venv/bin/activate

cd venv/cnaas-nms/src

nosetests --collect-only --with-id -v
nosetests --with-coverage --cover-package=cnaas_nms -v
cp .coverage /coverage/.coverage-nosetests

