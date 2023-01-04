#!/bin/bash

PYTESTARGS=()

if [ ! -z "$NO_EQUIPMENTTEST" ] ; then
	PYTESTARGS+=("-m" "not equipment")
fi

if [ ! -z "$COVERAGE" ] ; then
	PYTESTARGS+=("--cov=cnaas_nms" "-p" "no:cacheprovider")
fi

cd /opt/cnaas/venv/cnaas-nms/src/

source ../../bin/activate

echo "starting unittests: pytest ${PYTESTARGS[@]}"
pytest "${PYTESTARGS[@]}"
EXITSTATUS="$?"

if [ -f ".coverage" ] ; then
	mv .coverage .coverage-pytest
fi

exit $EXITSTATUS
