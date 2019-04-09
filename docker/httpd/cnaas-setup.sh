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
git clone --depth 1 --no-checkout --filter=blob:none https://github.com/SUNET/cnaas-nms.git cnaas-nms
cd cnaas-nms/
git checkout master -- templates/
