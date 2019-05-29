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
    && apt-get clean

#rm -rf /var/lib/apt/lists/*

#python3 -m venv /opt/cnaas/venv

#/opt/cnaas/venv/bin/pip install -U pip

#cd /opt/cnaas/venv/
#source bin/activate
#git clone https://github.com/SUNET/cnaas-nms.git
#cd cnaas-nms/
#python3 -m pip install -r requirements.txt

