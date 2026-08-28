# Stage 1: Builder - install dependencies
FROM python:3.13-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git libpcre2-dev libpq-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Create virtual environment
RUN uv venv /opt/cnaas/venv
ENV VIRTUAL_ENV=/opt/cnaas/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy version file first (needed for dynamic version in pyproject.toml)
COPY src/cnaas_nms/version.py /build/src/cnaas_nms/version.py
COPY pyproject.toml .

# Install Python dependencies
ARG INCLUDE_INTEGRATION_TOOLS=0
RUN uv pip install --no-cache . && \
    uv pip install --no-cache --group api-runtime && \
    if [ "$INCLUDE_INTEGRATION_TOOLS" = "1" ]; then \
        uv pip install --no-cache --group integration-tools; \
    fi

# Copy source code to build directory for patching
COPY src/ /build/src/

# Apply patches.
# - swaggeruirequestintercept.patch: allows Swagger UI request interceptor
#   to include credentials from browser local storage during manual API testing
COPY docker/api/swaggeruirequestintercept.patch /tmp/
RUN SITE_PACKAGES="$(/opt/cnaas/venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')" && \
    patch -d "$SITE_PACKAGES" -p1 < /tmp/swaggeruirequestintercept.patch || true

# Copy source code and alembic to venv location
COPY src/ /opt/cnaas/venv/cnaas-nms/src/
COPY alembic/ /opt/cnaas/venv/cnaas-nms/alembic/
COPY alembic.ini /opt/cnaas/venv/cnaas-nms/

# Stage 2: Runtime - minimal production image
FROM python:3.13-slim-trixie AS runtime

ARG GIT_COMMIT
ARG GIT_DATE
ARG GIT_BRANCH

ENV GIT_COMMIT=$GIT_COMMIT
ENV GIT_DATE=$GIT_DATE
ENV GIT_BRANCH=$GIT_BRANCH

RUN apt-get update && apt-get install -y --no-install-recommends \
    bind9-host curl git iputils-ping libpq5 \
    libyaml-dev net-tools netcat-openbsd nginx \
    openssl procps psmisc ssh-client \
    supervisor uwsgi-plugin-python3 \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/cnaas/templates /opt/cnaas/settings /etc/cnaas-nms /tmp/devicecerts \
    && chown -R www-data:www-data /opt/cnaas /etc/cnaas-nms /tmp/devicecerts

# Copy venv from builder
COPY --from=builder --chown=root:www-data /opt/cnaas/venv /opt/cnaas/venv
RUN chmod 555 /opt/cnaas/venv

# Copy nginx/supervisor configs
COPY docker/api/config/supervisord_app.conf /etc/supervisor/supervisord.conf
COPY docker/api/config/nginx_app.conf /etc/nginx/sites-available/
COPY docker/api/config/nginx.conf /etc/nginx/
COPY docker/api/cert/* /etc/nginx/conf.d/
COPY docker/api/config/gitconfig /var/www/.gitconfig
COPY --chown=root:www-data docker/api/config/uwsgi.ini /opt/cnaas/venv/cnaas-nms/
RUN chmod 444 /opt/cnaas/venv/cnaas-nms/uwsgi.ini

# Configure nginx
RUN unlink /etc/nginx/sites-enabled/default \
    && ln -s /etc/nginx/sites-available/nginx_app.conf /etc/nginx/sites-enabled/default \
    && chown -R www-data:www-data /var/log/nginx/ /var/lib/nginx/ \
    && chown -R root:www-data /etc/nginx/ \
    && chmod -R u=rwX,g=rX,o= /etc/nginx/

# Copy runtime scripts
COPY --chown=root:www-data docker/api/createca.sh docker/api/exec-pre-app.sh /opt/cnaas/
RUN chmod 555 /opt/cnaas/createca.sh /opt/cnaas/exec-pre-app.sh

# Copy cnaas configuration files
COPY --chown=root:www-data docker/api/config/api.yml docker/api/config/db_config.yml \
     docker/api/config/plugins.yml /etc/cnaas-nms/
# repository.yml is replaced by exec-pre-app.sh before uwsgi starts
COPY --chown=root:www-data docker/api/config/repository.yml /etc/cnaas-nms/
# Optional auth config (may not exist) - use glob pattern
COPY --chown=root:www-data docker/api/config/auth_config.ym[l] docker/api/config/permissions.ym[l] /etc/cnaas-nms/
RUN chmod 444 /etc/cnaas-nms/api.yml /etc/cnaas-nms/db_config.yml /etc/cnaas-nms/plugins.yml /etc/cnaas-nms/repository.yml /etc/cnaas-nms/auth_config.ym[l] /etc/cnaas-nms/permissions.ym[l]

USER www-data
EXPOSE 1443
ENTRYPOINT ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
