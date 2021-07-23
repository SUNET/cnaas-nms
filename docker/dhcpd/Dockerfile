FROM debian:buster
ARG BUILDBRANCH
ARG GITREPO_BASE

RUN mkdir -p /opt/cnaas \
    && mkdir /etc/cnaas-nms

COPY cnaas-setup.sh dhcp-hook.sh dhcpd.sh dhcpd.conf /opt/cnaas/
RUN /opt/cnaas/cnaas-setup.sh ${GITREPO_BASE} ${BUILDBRANCH}

COPY apiclient.yml /etc/cnaas-nms/apiclient.yml
COPY config/supervisord_app.conf /etc/supervisor/supervisord.conf

EXPOSE 67/udp

ENTRYPOINT supervisord -c /etc/supervisor/supervisord.conf
