FROM debian:buster

USER root

# Install system packages
RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get install -y --no-install-recommends \
      bind9-host \
      build-essential \
      curl \
      git \
      iputils-ping \
      libpcre2-dev \
      libpcre3-dev \
      libpq-dev \
      libssl-dev \
      net-tools \
      netcat \
      netcat-openbsd \
      nginx \
      procps \
      python3-dev \
      python3-pip \
      python3-setuptools \
      python3-venv \
      python3-wheel \
      python3-yaml \
      psmisc \
      supervisor \
      uwsgi-plugin-python3 \
    && pip3 install --no-cache-dir uwsgi

# Prepare for supervisord, ngninx
COPY config/supervisord_app.conf /etc/supervisor/supervisord.conf
COPY config/nginx_app.conf /etc/nginx/sites-available/
COPY config/nginx.conf /etc/nginx/
COPY cert/* /etc/nginx/conf.d/
# Prepare running nginx as www-data
RUN unlink /etc/nginx/sites-enabled/default \
    && ln -s /etc/nginx/sites-available/nginx_app.conf /etc/nginx/sites-enabled/default \
    && chown -R www-data:www-data /var/log/nginx/ \
    && chown -R www-data:www-data /var/lib/nginx/ \
    && chown -R root:www-data /etc/nginx/ \
    && chmod -R u=rwX,g=rX,o= /etc/nginx/

# Create cnaas directories
RUN mkdir -p /opt/cnaas /etc/cnaas-nms \
    && chown -R root:www-data /opt/cnaas /etc/cnaas-nms \
    && chmod -R u=rwX,g=rX,o= /opt/cnaas
RUN mkdir -p /opt/cnaas/templates /opt/cnaas/settings /opt/cnaas/venv \
    && chown www-data:www-data /opt/cnaas/templates /opt/cnaas/settings /opt/cnaas/venv

# Copy cnaas scripts
COPY --chown=root:www-data cnaas-setup.sh createca.sh exec-pre-app.sh nosetests.sh /opt/cnaas/

# Copy cnaas configuration files
COPY --chown=www-data:www-data config/api.yml config/db_config.yml config/plugins.yml config/repository.yml /etc/cnaas-nms/


USER www-data

# Give permission for devicecert store
RUN mkdir /tmp/devicecerts \
    && chmod -R u=rwX,g=,o= /tmp/devicecerts

ARG BUILDBRANCH=develop
ARG GITREPO_BASE=https://github.com/SUNET/cnaas-nms.git
# Branch specific, don't cache
ADD "https://api.github.com/repos/SUNET/cnaas-nms/git/refs/heads/" latest_commit
# Cnaas setup script
RUN /opt/cnaas/cnaas-setup.sh ${GITREPO_BASE} ${BUILDBRANCH}
# Freeze source
USER root
RUN chown -R root:www-data /opt/cnaas/venv/cnaas-nms/ && chmod -R u=rwX,g=rX,o= /opt/cnaas/venv/cnaas-nms/
USER www-data

# Prepare for uwsgi
COPY --chown=root:www-data config/uwsgi.ini /opt/cnaas/venv/cnaas-nms/


# Expose HTTPS
EXPOSE 1443

ENTRYPOINT supervisord -c /etc/supervisor/supervisord.conf
