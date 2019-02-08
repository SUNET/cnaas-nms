#!/bin/bash

cd /opt/cnaas/venv/cnaas-nms/src
source ../../bin/activate
python3 -m cnaas_nms.tools.dhcp_hook "$1" "$2" "$3"
