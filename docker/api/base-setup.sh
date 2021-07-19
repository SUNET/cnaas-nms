#!/bin/bash

set -xe

export DEBIAN_FRONTEND noninteractive


apt-get update && \
    apt-get -y dist-upgrade && \
    apt-get install -y --no-install-recommends \
      git \
      build-essential \
      python3-dev \
      python3-pip \
      python3-setuptools \
      python3-venv \
      python3-wheel \
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
