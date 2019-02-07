FROM debian:buster

RUN mkdir -p /opt/cnaas

COPY cnaas-setup.sh /opt/cnaas/cnaas-setup.sh

RUN /opt/cnaas/cnaas-setup.sh

COPY dhcpd.sh /opt/cnaas/dhcpd.sh
COPY dhcpd.conf /opt/cnaas/dhcpd.conf

ENTRYPOINT ["/opt/cnaas/dhcpd.sh"]
