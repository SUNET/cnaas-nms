#!/bin/bash

cd /opt/cnaas/venv/cnaas-nms/src/

source ../../bin/activate

pytest --cov=cnaas_nms -p no:cacheprovider
mv .coverage .coverage-pytest
