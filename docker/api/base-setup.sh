#!/bin/bash

set -xe

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
