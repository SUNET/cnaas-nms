FROM debian:buster

ENV DEBIAN_FRONTEND noninteractive

# Install freeradius
RUN apt update
RUN apt install -y freeradius

WORKDIR /etc/freeradius/3.0/

# Copy config directory
COPY config/ /root/config/

# Copy individual files
RUN cp /root/config/clients.conf .
RUN cp /root/config/mods-available/* mods-available/
RUN cp /root/config/mods-config/files/authorize mods-config/files/authorize

# Run freeradius with debug enabled
CMD /usr/sbin/freeradius -X -f
