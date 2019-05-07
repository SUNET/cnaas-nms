FROM debian:buster

ENV DEBIAN_FRONTEND noninteractive

RUN apt update
RUN apt install -y freeradius git

# Create directories
RUN mkdir /cnaas

WORKDIR /cnaas

# Fetch the code
RUN git clone https://github.com/SUNET/cnaas-nms.git /cnaas

COPY config/* /etc/freeradius/3.0/

CMD /usr/sbin/freeradius -X -f
