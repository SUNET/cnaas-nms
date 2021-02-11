FROM debian:buster
ARG BUILDBRANCH

RUN mkdir -p /opt/cnaas
RUN mkdir /etc/cnaas-nms

COPY cnaas-setup.sh /opt/cnaas/cnaas-setup.sh
RUN /opt/cnaas/cnaas-setup.sh ${BUILDBRANCH}

COPY dhcp-hook.sh /opt/cnaas/dhcp-hook.sh
COPY db_config.yml /etc/cnaas-nms/db_config.yml
COPY apiclient.yml /etc/cnaas-nms/apiclient.yml
COPY config/supervisord_app.conf /etc/supervisor/supervisord.conf
COPY dhcpd.sh /opt/cnaas/dhcpd.sh
COPY dhcpd.conf /opt/cnaas/dhcpd.conf

EXPOSE 67/udp

ENTRYPOINT supervisord -c /etc/supervisor/supervisord.conf
