FROM debian:buster

# Install package dependencies
RUN apt update
RUN apt install -y python3 python3-pip git python3-venv

# Create directories
RUN mkdir /cnaas
RUN mkdir -p /opt/cnaas
RUN mkdir /etc/cnaas-nms

# Start venv
RUN python3 -m venv /opt/cnaas/venv

WORKDIR /opt/cnaas/venv/

RUN sh ./bin/activate

# Fetch the code
RUN git clone https://github.com/SUNET/cnaas-nms.git

WORKDIR /opt/cnaas/venv/cnaas-nms/

RUN python3 -m pip install -r requirements.txt
COPY db_config.yml /etc/cnaas-nms/db_config.yml

WORKDIR /opt/cnaas/venv/cnaas-nms/src/

ENTRYPOINT PYTHONPATH=`pwd` python3 cnaas_nms/run.py
