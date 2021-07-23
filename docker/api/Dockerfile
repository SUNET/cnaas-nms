FROM debian:buster
ARG BUILDBRANCH=develop
ARG GITREPO_BASE=https://github.com/SUNET/cnaas-nms.git


# Install system packages
RUN apt-get update && \
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
    && apt-get clean \
    && pip3 install uwsgi

# Prepare for supervisord, ngninx
COPY config/supervisord_app.conf /etc/supervisor/supervisord.conf
COPY config/nginx_app.conf /etc/nginx/sites-available/
COPY config/nginx.conf /etc/nginx/
COPY cert/* /etc/nginx/conf.d/
# Prepare running nginx as www-data
RUN unlink /etc/nginx/sites-enabled/default
RUN ln -s /etc/nginx/sites-available/nginx_app.conf /etc/nginx/sites-enabled/default
RUN chown -R www-data:www-data /var/log/nginx/
RUN chown -R www-data:www-data /var/lib/nginx/
RUN chown -R root:www-data /etc/nginx/ && \
    chmod -R u=rwX,g=rX,o= /etc/nginx/

# Create cnaas directories
RUN mkdir -p /opt/cnaas/templates/
RUN mkdir /opt/cnaas/settings/
RUN mkdir /etc/cnaas-nms/

# Cnaas setup script
COPY cnaas-setup.sh /opt/cnaas/
COPY cnaas-setup-branch.sh /opt/cnaas/

# Prepare for tests
COPY nosetests.sh /opt/cnaas/
COPY createca.sh /opt/cnaas/

# Prepare for uwsgi
COPY exec-pre-app.sh /opt/cnaas/

# Copy cnaas configuration files
# db_config.yml, api.yml, repository.yml, plugins.yml
COPY config/*.yml /etc/cnaas-nms/
RUN chown www-data:www-data /etc/cnaas-nms/*.yml

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

RUN /opt/cnaas/cnaas-setup.sh ${GITREPO_BASE}
RUN chown -R www-data:www-data /opt/cnaas/venv/cnaas-nms/src/
# Prepare for uwsgi
COPY --chown=root:www-data config/uwsgi.ini /opt/cnaas/venv/cnaas-nms/
# Branch specific, don't cache
ADD "https://api.github.com/repos/SUNET/cnaas-nms/git/refs/heads/" latest_commit
RUN /opt/cnaas/cnaas-setup-branch.sh $BUILDBRANCH


# Expose HTTPS
EXPOSE 1443

ENTRYPOINT supervisord -c /etc/supervisor/supervisord.conf
