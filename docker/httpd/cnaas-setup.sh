#!/bin/bash

set -e
set -x

export DEBIAN_FRONTEND noninteractive

/bin/sed -i s/deb.debian.org/ftp.se.debian.org/g /etc/apt/sources.list


apt-get update && \
    apt-get -y dist-upgrade && \
    apt-get install -y \
      git \
      nginx \
      iputils-ping \
      procps \
      bind9-host \
      netcat-openbsd \
      net-tools \
      curl \
    && apt-get clean

#rm -rf /var/lib/apt/lists/*

cd /opt/cnaas/www

# this will be replaced by user defined repo at runtime if env variable GITREPO_TEMPLATES is set
git clone https://github.com/SUNET/cnaas-nms-templates templates
