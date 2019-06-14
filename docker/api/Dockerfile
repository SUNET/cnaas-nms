FROM debian:buster

# Create directories
RUN mkdir -p /opt/cnaas
RUN mkdir /etc/cnaas-nms

# Copy configuration files
COPY config/db_config.yml /etc/cnaas-nms/db_config.yml
COPY config/api.yml /etc/cnaas-nms/api.yml
COPY config/repository.yml /etc/cnaas-nms/repository.yml

# Setup script
COPY cnaas-setup.sh /opt/cnaas/cnaas-setup.sh
RUN /opt/cnaas/cnaas-setup.sh

# Prepare for supervisord, uwsgi, ngninx
COPY exec-pre-app.sh /opt/cnaas/
COPY config/uwsgi.ini /opt/cnaas/venv/cnaas-nms/
COPY config/supervisord_app.conf /etc/supervisor/conf.d
COPY config/nginx_app.conf /etc/nginx/sites-available/
COPY cert/* /etc/nginx/conf.d/

# Give nginx some special treatment
RUN unlink /etc/nginx/sites-enabled/default
RUN ln -s /etc/nginx/sites-available/nginx_app.conf /etc/nginx/sites-enabled/default

# Expose HTTPS
EXPOSE 443

ENTRYPOINT "supervisord"
