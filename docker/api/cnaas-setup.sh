#!/bin/bash

set -e
set -x

export DEBIAN_FRONTEND noninteractive


apt-get update && \
    apt-get -y dist-upgrade && \
    apt-get install -y \
      git \
      python3-venv \
      python3-pip \
      python3-yaml \
      iputils-ping \
      procps \
      bind9-host \
      netcat-openbsd \
      net-tools \
      curl \
      netcat \
      nginx \
      supervisor \
      libssl-dev \
      libpq-dev \
      libpcre2-dev \
      libpcre3-dev \
      uwsgi-plugin-python3 \
    && apt-get clean

pip3 install uwsgi

# Start venv
python3 -m venv /opt/cnaas/venv
cd /opt/cnaas/venv/
source bin/activate

/opt/cnaas/venv/bin/pip install -U pip

# Fetch the code and install dependencies
git clone "$1" cnaas-nms
cd cnaas-nms/
git config --add remote.origin.fetch "+refs/pull/*/head:refs/remotes/origin/pr/*"
python3 -m pip install -r requirements.txt

#rm -rf /var/lib/apt/lists/*


