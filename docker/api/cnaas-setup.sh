#!/bin/bash

set -e
set -x

export DEBIAN_FRONTEND noninteractive


# Start venv
python3 -m venv /opt/cnaas/venv
cd /opt/cnaas/venv/
source bin/activate

/opt/cnaas/venv/bin/pip install -U pip

# Fetch the code and install dependencies
git clone "$1" cnaas-nms
cd cnaas-nms/
# Checkout branch
git checkout --track origin/"$2"
git config --add remote.origin.fetch "+refs/pull/*/head:refs/remotes/origin/pr/*"
python3 -m pip install -r requirements.txt

#rm -rf /var/lib/apt/lists/*


