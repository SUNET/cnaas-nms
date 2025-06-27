#!/bin/sh

if [ -f "/tmp/pre-exec.lock" ]
then
	exit 0
else
	touch "/tmp/pre-exec.lock"
fi

cp /etc/cnaas-nms/repository.yml /tmp/repository.yml.original
sed -e "s|^\(templates_remote: \).\+$|\1 $GITREPO_TEMPLATES|" \
    -e "s|^\(settings_remote: \).\+$|\1 $GITREPO_SETTINGS|" \
  < /tmp/repository.yml.original > /tmp/repository.yml.new \
  && cat /tmp/repository.yml.new > /etc/cnaas-nms/repository.yml

set -e

# Wait for postgres to start
echo ">> Waiting for postgres to start"
WAIT=0
DB_HOSTNAME=`cat /etc/cnaas-nms/db_config.yml | awk '/^hostname/ {print $2}'`
while ! nc -z $DB_HOSTNAME 5432; do
    sleep 1
    WAIT=$(($WAIT + 1))
    if [ "$WAIT" -gt 15 ]; then
	echo "Error: Timeout wating for Postgres to start"
	exit 1
    fi
done

# Activate venv
cd /opt/cnaas/venv
. bin/activate

# Make sure database is up to date
(cd /opt/cnaas/venv/cnaas-nms/; alembic upgrade head)
if [ $? -ne 0 ]; then
    echo "Error: Failed to run Alembic"
    exit 1
fi
