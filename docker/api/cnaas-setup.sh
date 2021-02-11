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
git clone https://github.com/SUNET/cnaas-nms.git
cd cnaas-nms/
git checkout $1
python3 -m pip install -r requirements.txt

chown -R www-data:www-data /opt/cnaas/settings
chown -R www-data:www-data /opt/cnaas/templates
#rm -rf /var/lib/apt/lists/*


