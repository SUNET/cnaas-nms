#!/bin/bash

PYTESTARGS=""

if [ ! -z "$NO_EQUIPMENTTEST" ] ; then
	PYTESTARGS="-m 'not equipment'"
fi

cd /opt/cnaas/venv/cnaas-nms/src/

source ../../bin/activate

pytest --cov=cnaas_nms -p no:cacheprovider $PYTESTARGS
EXITSTATUS="$?"
mv .coverage .coverage-pytest

exit $EXITSTATUS
