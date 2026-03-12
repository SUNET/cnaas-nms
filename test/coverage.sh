#!/bin/bash

cd /opt/cnaas/venv/cnaas-nms/src/

source ../../bin/activate

ls -l .coverage-*
python -m coverage combine .coverage-*
python -m coverage report --omit='*/site-packages/*'
python -m coverage xml -i --omit='*/site-packages/*,*/templates/*'

export CODECOV_TOKEN="dbe13a97-70b5-49df-865e-d9b58c4e9742"
bash <(curl -s https://codecov.io/bash)
