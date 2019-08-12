#!/bin/sh

set -e

sed -e "s|^\(templates_remote: \).\+$|\1 $GITREPO_TEMPLATES|" \
    -e "s|^\(settings_remote: \).\+$|\1 $GITREPO_SETTINGS|" \
  < /etc/cnaas-nms/repository.yml > /tmp/repository.yml.new \
  && cat /tmp/repository.yml.new > /etc/cnaas-nms/repository.yml

if [ -e "/opt/cnaas/settings" ]; then
    rm -rf /opt/cnaas/settings
fi

if [ -e "/opt/cnaas/templates" ]; then
    rm -rf /opt/cnaas/templates
fi

git clone $GITREPO_SETTINGS /opt/cnaas/settings
git clone $GITREPO_TEMPLATES /opt/cnaas/templates

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

# Activate venv
cd /opt/cnaas/venv
. bin/activate

# Make sure database is up to date
(cd /opt/cnaas/venv/cnaas-nms/; alembic upgrade head)
if [ $? -ne 0 ]; then
    echo "Error: Failed to run Alembic"
    exit 1
fi

# Clean old coverage reports if they exist
set +e
if [ -e /coverage/.coverage ]; then
    rm /coverage/.coverage*
fi

# Temporary for dev
#cd /opt/cnaas/venv/
#. bin/activate
#cd /opt/cnaas/venv/cnaas-nms/
#git pull
#python3 -m pip install -r requirements.txt

