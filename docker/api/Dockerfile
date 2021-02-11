FROM debian:buster
ARG BUILDBRANCH
ARG GITREPO_BASE

# Create directories
RUN mkdir -p /opt/cnaas/templates/
RUN mkdir /opt/cnaas/settings/
RUN mkdir /etc/cnaas-nms/

# Copy configuration files
# db_config.yml, api.yml, repository.yml, plugins.yml
COPY config/*.yml /etc/cnaas-nms/

# Setup script
COPY cnaas-setup.sh /opt/cnaas/
RUN /opt/cnaas/cnaas-setup.sh ${GITREPO_BASE} ${BUILDBRANCH}

# Prepare for supervisord, uwsgi, ngninx
COPY nosetests.sh /opt/cnaas/
COPY exec-pre-app.sh /opt/cnaas/
COPY createca.sh /opt/cnaas/
COPY --chown=root:www-data config/uwsgi.ini /opt/cnaas/venv/cnaas-nms/
COPY config/supervisord_app.conf /etc/supervisor/supervisord.conf
COPY config/nginx_app.conf /etc/nginx/sites-available/
COPY config/nginx.conf /etc/nginx/
COPY cert/* /etc/nginx/conf.d/

# Websocket test client
RUN mkdir /opt/cnaas/static/
COPY client.html /opt/cnaas/static/

# Give nginx some special treatment
RUN unlink /etc/nginx/sites-enabled/default
RUN ln -s /etc/nginx/sites-available/nginx_app.conf /etc/nginx/sites-enabled/default
RUN chown www-data:www-data /etc/cnaas-nms/*.yml
RUN chown -R www-data:www-data /var/log/nginx/
RUN chown -R www-data:www-data /var/lib/nginx/
RUN chown -R root:www-data /etc/nginx/ && \
    chmod -R u=rwX,g=rX,o= /etc/nginx/
# Give permission for API to clone/sync repos
RUN chown -R root:www-data /opt/cnaas/ && \
    chmod -R u=rwX,g=rX,o= /opt/cnaas/
RUN chown -R www-data:www-data /opt/cnaas/templates/
RUN chown -R www-data:www-data /opt/cnaas/settings/
# Give permission for devicecert store
RUN mkdir /tmp/devicecerts
RUN chown -R www-data:www-data /tmp/devicecerts && \
    chmod -R u=rwX,g=,o= /tmp/devicecerts
# Give permission for unittests
RUN chown root:www-data /opt/cnaas/*.sh && \
    chmod g+rx /opt/cnaas/*.sh
RUN chown -R www-data:www-data /opt/cnaas/venv/cnaas-nms/src/


# Expose HTTPS
EXPOSE 1443

ENTRYPOINT supervisord -c /etc/supervisor/supervisord.conf
