FROM debian:buster

# Install package dependencies
RUN apt update
RUN apt install -y python3 python3-pip git python3-venv netcat python3-yaml

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

RUN pip3 install -r requirements.txt
COPY db_config.yml /etc/cnaas-nms/db_config.yml
COPY api.yml /etc/cnaas-nms/api.yml
COPY repository.yml /etc/cnaas-nms/repository.yml
COPY entrypoint.sh /usr/local/bin/

WORKDIR /opt/cnaas/venv/cnaas-nms/src/

EXPOSE 5001

CMD sh /usr/local/bin/entrypoint.sh

#ENTRYPOINT PYTHONPATH=`pwd` python3 cnaas_nms/run.py
