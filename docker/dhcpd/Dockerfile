FROM debian:buster
ARG BUILDBRANCH
ARG GITREPO_BASE

RUN mkdir -p /opt/cnaas /etc/cnaas-nms

COPY cnaas-setup.sh /opt/cnaas/
RUN /opt/cnaas/cnaas-setup.sh ${GITREPO_BASE} ${BUILDBRANCH}

COPY config/dhcp-hook.sh config/dhcpd.sh config/dhcpd.conf /opt/cnaas/
COPY config/apiclient.yml /etc/cnaas-nms/
COPY config/supervisord_app.conf /etc/supervisor/

EXPOSE 67/udp

ENTRYPOINT supervisord -c /etc/supervisor/supervisord.conf
