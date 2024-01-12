#!/bin/bash

set -e
set -x

export DEBIAN_FRONTEND noninteractive


# Start venv
python3.11 -m venv /opt/cnaas/venv
cd /opt/cnaas/venv/
source bin/activate

/opt/cnaas/venv/bin/pip install --no-cache-dir -U pip

# Fetch the code
git clone $1 cnaas-nms
cd cnaas-nms/
# switch to $BUILDBRANCH
git config --add remote.origin.fetch "+refs/pull/*/head:refs/remotes/origin/pr/*"
git fetch --all
git checkout $2
python --version
# install dependencies
python3 -m pip install --no-cache-dir uwsgi
python3 -m pip install --no-cache-dir -r requirements.txt
