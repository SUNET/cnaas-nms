FROM debian:buster
ARG BUILDBRANCH=develop
ARG GITREPO_BASE=https://github.com/SUNET/cnaas-nms.git

# Base setup
USER root
RUN mkdir -p /opt/cnaas
COPY base-setup.sh cnaas-setup.sh /opt/cnaas/
RUN /opt/cnaas/base-setup.sh

# Create directories
RUN mkdir -p /opt/cnaas/templates/ /opt/cnaas/settings/ /etc/cnaas-nms/

# Copy configuration files
# db_config.yml, api.yml, repository.yml, plugins.yml
COPY --chown=www-data:www-data config/*.yml /etc/cnaas-nms/

# Setup script
RUN /opt/cnaas/cnaas-setup.sh ${GITREPO_BASE} ${BUILDBRANCH}

COPY nosetests.sh /opt/cnaas/
# Prepare for supervisord, uwsgi, ngninx
COPY config/exec-pre-app.sh createca.sh /opt/cnaas/
COPY --chown=root:www-data config/uwsgi.ini /opt/cnaas/venv/cnaas-nms/
COPY config/supervisord_app.conf /etc/supervisor/supervisord.conf
COPY config/nginx_app.conf /etc/nginx/sites-available/
COPY config/nginx.conf /etc/nginx/
COPY cert/* /etc/nginx/conf.d/

# Run nginx as www-data
RUN unlink /etc/nginx/sites-enabled/default \
    && ln -s /etc/nginx/sites-available/nginx_app.conf /etc/nginx/sites-enabled/default \
    && chown -R www-data:www-data /var/log/nginx/ \
    && chown -R www-data:www-data /var/lib/nginx/ \
    && chown -R root:www-data /etc/nginx/ \
    && chmod -R u=rwX,g=rX,o= /etc/nginx/
# Give permission for API to clone/sync repos
RUN chown -R root:www-data /opt/cnaas/ \
    && chmod -R u=rwX,g=rX,o= /opt/cnaas/ \
    && chown -R www-data:www-data /opt/cnaas/templates/ \
    && chown -R www-data:www-data /opt/cnaas/settings/
# Give permission for devicecert store
RUN mkdir -p /tmp/devicecerts \
    && chown -R www-data:www-data /tmp/devicecerts \
    && chmod -R u=rwX,g=,o= /tmp/devicecerts
# Give permission for unittests
RUN chown root:www-data /opt/cnaas/*.sh \
    && chmod g+rx /opt/cnaas/*.sh \
    && chown -R www-data:www-data /opt/cnaas/venv/cnaas-nms/src/

# Branch specific, don't cache
ADD "https://api.github.com/repos/SUNET/cnaas-nms/git/refs/heads/" latest_commit

# Expose HTTPS
EXPOSE 1443

ENTRYPOINT supervisord -c /etc/supervisor/supervisord.conf
