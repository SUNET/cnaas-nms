# Stage 1: Builder - install dependencies
FROM python:3.13-slim-trixie AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libpcre2-dev libssl-dev git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN python -m venv /opt/cnaas/venv

# Copy source code first (needed for dynamic version in pyproject.toml)
COPY src/ /build/src/
COPY pyproject.toml .

# Install Python dependencies
ARG INCLUDE_INTEGRATION_TOOLS=0
RUN /opt/cnaas/venv/bin/pip install --no-cache-dir -U pip && \
    /opt/cnaas/venv/bin/pip install --no-cache-dir . && \
    /opt/cnaas/venv/bin/pip install --no-cache-dir --group /build/pyproject.toml:api-runtime && \
    if [ "$INCLUDE_INTEGRATION_TOOLS" = "1" ]; then \
        /opt/cnaas/venv/bin/pip install --no-cache-dir --group /build/pyproject.toml:integration-tools; \
    fi

# Apply patches.
# - pull2167.patch: Napalm EOS 4.32 config-session compatibility fix
# - swaggeruirequestintercept.patch: allows Swagger UI request interceptor
#   to include credentials from browser local storage during manual API testing
COPY docker/api/pull2167.patch docker/api/swaggeruirequestintercept.patch /tmp/
RUN SITE_PACKAGES="$(/opt/cnaas/venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')" && \
    cd "$SITE_PACKAGES" && \
    patch -p1 < /tmp/pull2167.patch || true && \
    patch -p1 < /tmp/swaggeruirequestintercept.patch || true

# Copy source code and alembic to venv location
COPY src/ /opt/cnaas/venv/cnaas-nms/src/
COPY alembic/ /opt/cnaas/venv/cnaas-nms/alembic/
COPY alembic.ini /opt/cnaas/venv/cnaas-nms/


# Stage 2: Runtime - minimal production image
FROM python:3.13-slim-trixie AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 nginx supervisor ssh-client \
    bind9-host iputils-ping net-tools netcat-openbsd procps psmisc \
    curl uwsgi-plugin-python3 git openssl \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/cnaas/templates /opt/cnaas/settings /etc/cnaas-nms /tmp/devicecerts \
    && chown -R www-data:www-data /opt/cnaas /etc/cnaas-nms /tmp/devicecerts

# Copy venv from builder
COPY --chmod=555 --from=builder --chown=root:www-data /opt/cnaas/venv /opt/cnaas/venv

# Copy over .git folder to get git commit hash in the UI.
# Should be changed later to another method
COPY .git /opt/cnaas/venv/cnaas-nms/.git

# Copy nginx/supervisor configs
COPY docker/api/config/supervisord_app.conf /etc/supervisor/supervisord.conf
COPY docker/api/config/nginx_app.conf /etc/nginx/sites-available/
COPY docker/api/config/nginx.conf /etc/nginx/
COPY docker/api/cert/* /etc/nginx/conf.d/
COPY docker/api/config/gitconfig /var/www/.gitconfig
COPY --chmod=444 --chown=root:www-data docker/api/config/uwsgi.ini /opt/cnaas/venv/cnaas-nms/

# Configure nginx
RUN unlink /etc/nginx/sites-enabled/default \
    && ln -s /etc/nginx/sites-available/nginx_app.conf /etc/nginx/sites-enabled/default \
    && chown -R www-data:www-data /var/log/nginx/ /var/lib/nginx/ \
    && chown -R root:www-data /etc/nginx/ \
    && chmod -R u=rwX,g=rX,o= /etc/nginx/

# Copy runtime scripts
COPY --chmod=555 --chown=root:www-data docker/api/createca.sh docker/api/exec-pre-app.sh /opt/cnaas/

# Copy cnaas configuration files
COPY --chmod=444 --chown=root:www-data docker/api/config/api.yml docker/api/config/db_config.yml \
     docker/api/config/plugins.yml /etc/cnaas-nms/
# repository.yml is replaced by exec-pre-app.sh before uwsgi starts
COPY --chmod=444 --chown=root:www-data docker/api/config/repository.yml /etc/cnaas-nms/
# Optional auth config (may not exist) - use glob pattern
COPY --chmod=444 --chown=root:www-data docker/api/config/auth_config.ym[l] docker/api/config/permissions.ym[l] /etc/cnaas-nms/

USER www-data
EXPOSE 1443
ENTRYPOINT ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
