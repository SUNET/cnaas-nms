#!/bin/sh

POSTGRES_DB="cnaas"
POSTGRES_PORT=5432
POSTGRES_USER="cnaas"
POSTGRES_PASSWORD="cnaas"
POSTGRES_ADDR=

CNAAS_COMPONENTS="api dhcpd httpd"

USERNAME_DHCP_BOOT="admin"
PASSWORD_DHCP_BOOT="abc123abc123"
USERNAME_DISCOVERED="admin"
PASSWORD_DISCOVERED="abc123abc123"
USERNAME_INIT="admin"
PASSWORD_INIT="abc123abc123"
USERNAME_MANAGED="admin"
PASSWORD_MANAGED="abc123abc123"

config_write() {
    for i in $CNAAS_COMPONENTS; do
	echo "type: postgresql" > ${i}/db_config.yml
	echo "hostname: $POSTGRES_ADDR" >> ${i}/db_config.yml
	echo "port: $POSTGRES_PORT" >> ${i}/db_config.yml
	echo "username: $POSTGRES_USER" >> ${i}/db_config.yml
	echo "password: $POSTGRES_PASSWORD" >> ${i}/db_config.yml
	echo "database: $POSTGRES_DB" >> ${i}/db_config.yml
    done
}

start_postgres() {
    container_id=$(docker run -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
			  -e POSTGRES_USER=$POSTGRES_USER \
			  -e POSTGRES_DB=$POSTGRES_DB \
			  -p $POSTGRES_PORT:5432 \
			  --name cnaas_postgres -d postgres)

    if [ $? -ne 0 ]; then
	echo "Failed to start postgres"
	exit
    fi

    sleep 10

    POSTGRES_ADDR=$(docker inspect -f \
			   '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' \
			   $container_id)
}

start_cnaas() {
    for i in $CNAAS_COMPONENTS; do

	echo "Starting $i"

	docker pull docker.sunet.se/cnaas/${i}:latest

	if [ $? -ne 0 ]; then
	    echo "Failed to build container for $i"
	    exit
	fi

	docker run -d -it --name "cnaas_${i}" "cnaas-nms/${i}:latest"

	if [ $? -ne 0 ]; then
	    echo "Failed to start container for $i"
	    exit
	fi
    done
}

container_info() {
    for i in $CNAAS_COMPONENTS postgres; do
	echo "${i}: $(docker inspect -f \
		    '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' \
		    cnaas_${i})"
    done
}

main() {


    start_postgres
    config_write
    start_cnaas
    container_info
}


main "$@"
