#!/bin/sh

CNAAS_COMPONENTS="postgres api dhcpd httpd"

docker_stop_cnaas() {
    for i in $CNAAS_COMPONENTS; do

	echo "Stopping $i"

	docker stop "cnaas_${i}"
	docker rm "cnaas_${i}"
    done
}

main() {
    docker_stop_cnaas
}

main "$@"
