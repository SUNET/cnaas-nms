#!/bin/bash

set -xe

export DEBIAN_FRONTEND noninteractive


# Create venv
python3 -m venv "$CNAAS_VENV"

# Fetch cnaas-nms code
git clone "$1" "$CNAAS_VENV"/cnaas-nms
cd "$CNAAS_VENV"/cnaas-nms
# Checkout branch
git checkout --track origin/"$2"
git config --add remote.origin.fetch "+refs/pull/*/head:refs/remotes/origin/pr/*"

# Enable venv, install requirements for cnaas-nms
PATH="$CNAAS_VENV/bin:$PATH"
python3 -m pip install --no-cache-dir -U pip
python3 -m pip install --no-cache-dir -r requirements.txt
