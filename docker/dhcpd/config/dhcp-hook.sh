#!/bin/bash

set -e

source /opt/cnaas/venv/bin/activate

cd /opt/cnaas/venv/cnaas-nms/src
python3 -m cnaas_nms.tools.dhcp_hook "$1" "$2" "$3" "$4"
