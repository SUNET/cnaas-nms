FROM debian:buster

RUN mkdir -p /opt/cnaas
RUN mkdir /etc/cnaas-nms

COPY cnaas-setup.sh /opt/cnaas/cnaas-setup.sh
COPY db_config.yml.sample /etc/cnaas-nms/db_config.yml
COPY dhcp-hook.sh /etc/cnaas-nms/dhcp-hook.sh

RUN /opt/cnaas/cnaas-setup.sh

COPY dhcpd.sh /opt/cnaas/dhcpd.sh
COPY dhcpd.conf /opt/cnaas/dhcpd.conf

ENTRYPOINT ["/opt/cnaas/dhcpd.sh"]
