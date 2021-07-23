FROM debian:buster

RUN mkdir -p /opt/cnaas \
    && mkdir /etc/cnaas-nms

COPY apiclient.yml /etc/cnaas-nms/apiclient.yml
COPY config/supervisord_app.conf /etc/supervisor/supervisord.conf
COPY cnaas-setup.sh dhcp-hook.sh dhcpd.sh dhcpd.conf /opt/cnaas/

ARG BUILDBRANCH
ARG GITREPO_BASE
RUN /opt/cnaas/cnaas-setup.sh ${GITREPO_BASE} ${BUILDBRANCH}

EXPOSE 67/udp

ENTRYPOINT supervisord -c /etc/supervisor/supervisord.conf
