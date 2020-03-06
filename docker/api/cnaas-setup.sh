#!/bin/bash

set -e
set -x

export DEBIAN_FRONTEND noninteractive

/bin/sed -i s/deb.debian.org/ftp.se.debian.org/g /etc/apt/sources.list

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
git checkout develop
python3 -m pip install -r requirements.txt

# Temporary for testing new branch
#cd /opt/cnaas/venv/cnaas-nms/
#git remote update
#git fetch
#git checkout --track origin/release-1.0.0
#python3 -m pip install -r requirements.txt

chown -R www-data:www-data /opt/cnaas/settings
chown -R www-data:www-data /opt/cnaas/templates
#rm -rf /var/lib/apt/lists/*


