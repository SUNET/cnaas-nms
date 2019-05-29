FROM debian:buster

# Install package dependencies
RUN apt update
RUN apt install -y python3 python3-pip git python3-venv netcat \
	python3-yaml nginx supervisor
RUN pip3 install uwsgi

# Create directories
RUN mkdir /cnaas
RUN mkdir -p /opt/cnaas
RUN mkdir /etc/cnaas-nms

# Start venv
RUN python3 -m venv /opt/cnaas/venv
WORKDIR /opt/cnaas/venv/
RUN sh ./bin/activate

# Fetch the code and install dependencies
RUN git clone https://github.com/SUNET/cnaas-nms.git
WORKDIR /opt/cnaas/venv/cnaas-nms/
RUN pip3 install -r requirements.txt

# Copy configuration files
COPY config/db_config.yml /etc/cnaas-nms/db_config.yml
COPY config/api.yml /etc/cnaas-nms/api.yml
COPY config/repository.yml /etc/cnaas-nms/repository.yml
COPY entrypoint.sh /usr/local/bin/
COPY config/uwsgi.ini /opt/cnaas/venv/cnaas-nms/
COPY config/supervisord_app.conf /etc/supervisor/conf.d
COPY config/nginx_app.conf /etc/nginx/sites-available/
COPY cert/* /etc/nginx/conf.d/

# Give nginx some special treatment
RUN unlink /etc/nginx/sites-enabled/default
RUN ln -s /etc/nginx/sites-available/nginx_app.conf /etc/nginx/sites-enabled/default

COPY run.py /opt/cnaas/venv/cnaas-nms/src/cnaas_nms/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Expose HTTPS
EXPOSE 443

ENTRYPOINT "supervisord"
