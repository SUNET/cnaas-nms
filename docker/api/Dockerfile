FROM debian:buster
ARG BUILDBRANCH=develop
ARG GITREPO_BASE=https://github.com/SUNET/cnaas-nms.git


USER root

# Base setup
RUN mkdir -p /opt/cnaas \
    && chown -R root:www-data /opt/cnaas/ \
    && chmod -R u=rwX,g=rX,o= /opt/cnaas/
COPY --chown=root:www-data base-setup.sh cnaas-setup.sh createca.sh nosetests.sh config/exec-pre-app.sh /opt/cnaas/
RUN /opt/cnaas/base-setup.sh

# Supervisord, nginx config
COPY config/supervisord_app.conf /etc/supervisor/supervisord.conf
COPY config/nginx_app.conf /etc/nginx/sites-available/
COPY config/nginx.conf /etc/nginx/
COPY cert/cnaas_snakeoil.crt cert/cnaas_snakeoil.key /etc/nginx/conf.d/
# Prepare running nginx as www-data
RUN unlink /etc/nginx/sites-enabled/default \
    && ln -s /etc/nginx/sites-available/nginx_app.conf /etc/nginx/sites-enabled/default \
    && chown -R root:www-data /etc/nginx/ \
    && chmod -R u=rwX,g=rX,o= /etc/nginx/ \
    && chown -R www-data:www-data /var/log/nginx/ \
    && chown -R www-data:www-data /var/lib/nginx/

# Create directories for www-data
RUN mkdir -p /opt/cnaas/templates /opt/cnaas/settings /opt/cnaas/venv /etc/cnaas-nms \
    && chown www-data:www-data /opt/cnaas/templates /opt/cnaas/settings /opt/cnaas/venv /etc/cnaas-nms


USER www-data

# Give permission for devicecert store
RUN mkdir -p /tmp/devicecerts \
    && chmod -R u=rwX,g=,o= /tmp/devicecerts

# Copy cnaas configuration files
COPY --chown=www-data:www-data config/api.yml config/db_config.yml config/plugins.yml config/repository.yml /etc/cnaas-nms/

# Branch specific, don't cache
ADD "https://api.github.com/repos/SUNET/cnaas-nms/git/refs/heads/" latest_commit
# Setup script
RUN /opt/cnaas/cnaas-setup.sh ${GITREPO_BASE} ${BUILDBRANCH}

# Prepare for uwsgi
COPY --chown=root:www-data config/uwsgi.ini /opt/cnaas/venv/cnaas-nms/


# Expose HTTPS
EXPOSE 1443

ENTRYPOINT supervisord -c /etc/supervisor/supervisord.conf
