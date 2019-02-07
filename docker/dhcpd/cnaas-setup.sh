#!/bin/bash

set -e
set -x

export DEBIAN_FRONTEND noninteractive

/bin/sed -i s/deb.debian.org/ftp.se.debian.org/g /etc/apt/sources.list


apt-get update && \
    apt-get -y dist-upgrade && \
    apt-get install -y \
      isc-dhcp-server \
      git \
      python3-venv \
      iputils-ping \
      procps \
      bind9-host \
      netcat-openbsd \
      net-tools \
      curl \
    && apt-get clean

rm -rf /var/lib/apt/lists/*

python3 -m venv /opt/cnaas/venv

/opt/cnaas/venv/bin/pip install -U pip
