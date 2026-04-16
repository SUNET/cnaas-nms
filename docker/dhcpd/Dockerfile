FROM debian:trixie-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    isc-dhcp-server python3-venv supervisor bind9-host git \
    iputils-ping procps net-tools curl netcat-openbsd \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/cnaas /etc/cnaas-nms \
    # Create minimal venv with only required deps
    && python3 -m venv /opt/cnaas/venv \
    && /opt/cnaas/venv/bin/pip install --no-cache-dir requests pyyaml netaddr jinja2 \
    # Create package directories for dhcp_hook module
    && mkdir -p /opt/cnaas/venv/cnaas-nms/src/cnaas_nms/tools

COPY --chmod=444 src/cnaas_nms/tools/dhcp_hook.py /opt/cnaas/venv/cnaas-nms/src/cnaas_nms/tools/

# Copy configs and scripts
COPY --chmod=444 docker/dhcpd/apiclient.yml /etc/cnaas-nms/
COPY --chmod=444 docker/dhcpd/config/supervisord_app.conf /etc/supervisor/supervisord.conf
COPY --chmod=555 docker/dhcpd/dhcp-hook.sh docker/dhcpd/dhcpd.sh /opt/cnaas/
COPY --chmod=444 docker/dhcpd/dhcpd.conf /opt/cnaas/

EXPOSE 67/udp
ENTRYPOINT ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
