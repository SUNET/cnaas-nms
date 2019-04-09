FROM debian:buster

RUN mkdir -p /opt/cnaas/www

VOLUME ["/opt/cnaas/www/firmware"]

COPY cnaas-setup.sh /opt/cnaas/cnaas-setup.sh
COPY httpd.sh /opt/cnaas/httpd.sh
COPY nginx.conf /opt/cnaas/nginx.conf

RUN /opt/cnaas/cnaas-setup.sh

EXPOSE 80

ENTRYPOINT ["/opt/cnaas/httpd.sh"]
