#!/bin/sh

# Wait for postgres to start
echo ">> Waiting for postgres to start"
WAIT=0
while ! nc -z cnaas_postgres 5432; do
    sleep 1
    WAIT=$(($WAIT + 1))
    if [ "$WAIT" -gt 15 ]; then
	echo "Error: Timeout wating for Postgres to start"
	exit 1
    fi
done

# Make sure database is up to date
(cd /opt/cnaas/venv/cnaas-nms/; alembic upgrade head)
if [ $? -ne 0 ]; then
    echo "Error: Failed to run Alembic"
    exit 1
fi

# Make sure we don't quit
sleep infinity
