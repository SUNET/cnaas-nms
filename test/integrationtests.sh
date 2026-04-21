#!/bin/bash

export GITREPO_TEMPLATES="https://github.com/SUNET/cnaas-integrationtest-templates.git"
export GITREPO_SETTINGS="https://github.com/SUNET/cnaas-integrationtest-settings.git"
export GITREPO_ETC="https://github.com/SUNET/cnaas-integrationtest-etc.git"
export USERNAME_DHCP_BOOT="admin"
export PASSWORD_DHCP_BOOT="abc123abc123"
export USERNAME_DISCOVERED="admin"
export PASSWORD_DISCOVERED="abc123abc123"
export USERNAME_INIT="admin"
export PASSWORD_INIT="abc123abc123"
export USERNAME_MANAGED="admin"
export PASSWORD_MANAGED="abc123abc123"
export COVERAGE=1
export EXTERNAL_TEST_CONTAINERS=1
export PYTEST_SETTINGS_CLONED=1
export PYTEST_TEMPLATES_CLONED=1
export OIDC_ENABLED=0
export PERMISSIONS_DISABLED=1
export JWT_AUTH_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiJ9.eyJpYXQiOjE1NzEwNTk2MTgsIm5iZiI6MTU3MTA1OTYxOCwianRpIjoiNTQ2MDk2YTUtZTNmOS00NzFlLWE2NTctZWFlYTZkNzA4NmVhIiwic3ViIjoiYWRtaW4iLCJmcmVzaCI6ZmFsc2UsInR5cGUiOiJhY2Nlc3MifQ.Sfffg9oZg_Kmoq7Oe8IoTcbuagpP6nuUXOQzqJpgDfqDq_GM_4zGzt7XxByD4G0q8g4gZGHQnV14TpDer2hJXw"
export JWT_SECRET_KEY="integrationtestkey"

# select docker compose v 1 or 2
docker compose >/dev/null 2>&1
if [[ $? -eq 1 ]]; then
	echo "detected docker-compose v1"
	COMPOSE_COMMAND="docker-compose -f ../docker/docker-compose.yaml"
else
	echo "detected docker compose v2"
	COMPOSE_COMMAND="docker compose -f ../docker/docker-compose.yaml"
	export COMPOSE_COMPATIBILITY=1
fi


on_exit() {
	$COMPOSE_COMMAND logs cnaas_dhcpd
	$COMPOSE_COMMAND logs cnaas_api
	echo "Integrationtests exited (on_exit)"
}

on_err() {
	$COMPOSE_COMMAND logs -n 100 cnaas_api
}

trap on_exit EXIT
trap on_err ERR

start_docker_environment() {
	echo "Starting docker environment"
	# Shut down old env if there is one
	$COMPOSE_COMMAND down -t 3

	# Reset database
	if docker volume ls | egrep -q "cnaas-postgres-data$"; then
		if [[ -z "$AUTOTEST" ]]; then
			read -p "Do you want to continue and reset existing SQL database? [y/N]" ans
			case $ans in
				[Yy]* ) docker volume rm cnaas-postgres-data ;;
				* ) exit 1 ;;
			esac
		else
			docker volume rm cnaas-postgres-data
		fi
	fi

	docker volume create cnaas-templates
	docker volume create cnaas-settings
	docker volume create cnaas-postgres-data
	docker volume create cnaas-jwtcert
	docker volume create cnaas-cacert

	$COMPOSE_COMMAND up -d

	$COMPOSE_COMMAND cp ../docker/jwt-cert/public.pem cnaas_api:/opt/cnaas/jwtcert/public.pem
	$COMPOSE_COMMAND exec -u root -T cnaas_api /bin/chown -R www-data:www-data /opt/cnaas/jwtcert/
	$COMPOSE_COMMAND exec -u root -T cnaas_api /opt/cnaas/createca.sh
	echo "Docker environment started"
}

setup_test_utilities() {
	echo "Setting up test utilities in api container"
	$COMPOSE_COMMAND cp ../pyproject.toml cnaas_api:/opt/cnaas/venv/cnaas-nms/
	$COMPOSE_COMMAND cp ../pytest.ini cnaas_api:/opt/cnaas/venv/cnaas-nms/
	$COMPOSE_COMMAND cp ../test/pytest.sh cnaas_api:/opt/cnaas/
	$COMPOSE_COMMAND cp ../test/coverage.sh cnaas_api:/opt/cnaas/
	$COMPOSE_COMMAND cp ../src/.coveragerc cnaas_api:/opt/cnaas/venv/cnaas-nms/src/
	$COMPOSE_COMMAND exec -u root -T cnaas_api /bin/bash -c \
		'chown www-data:www-data /opt/cnaas/pytest.sh /opt/cnaas/coverage.sh /opt/cnaas/venv/cnaas-nms/src/.coveragerc && \
		chmod ug+x /opt/cnaas/pytest.sh /opt/cnaas/coverage.sh && \
		cd /opt/cnaas/venv/cnaas-nms && \
		source ../bin/activate && \
		pip install -q --group dev && \
		chmod ug+w src && \
		supervisorctl stop uwsgi && \
		rm src/.coverage-*'

	echo "Trying to reset api container logs"
	API_CONTAINER_NAME=$($COMPOSE_COMMAND ps | grep cnaas_api | awk '{print $1}')

	LOGPATH=$(docker inspect --format='{{.LogPath}}' $API_CONTAINER_NAME)

	# This needs to be run as sudo
	# Move on if this step fails.
	if [[ -z "$AUTOTEST" ]]; then
		sudo truncate -s 0 "$LOGPATH" || true
	else
		sudo -n truncate -s 0 "$LOGPATH" || true
	fi

	$COMPOSE_COMMAND exec -u root -T cnaas_api /bin/bash -c 'supervisorctl start uwsgi'
}

wait_for_api() {
	echo "Waiting for API to become ready..."

	for i in {1..60}; do
        # Extract just the HTTP response code
        status_code=$(curl -ks -o /dev/null -w "%{http_code}" https://localhost/api/v1.0/system/version)

        if [[ "$status_code" -eq 200 ]]; then
            echo "API is up! (HTTP 200)"
            # Show version
            curl -ks https://localhost/api/v1.0/system/version
            return 0
        fi
        
        # Pause for 1 second before checking again
        sleep 1
    done

    echo "Error: API did not become ready in time. Last status code was $status_code."
    exit 1
}

start_integration_tests() {
	if [[ ! -z "$PRE_TEST_SCRIPT" && -x "$PRE_TEST_SCRIPT" ]]; then
		echo "Running PRE_TEST_SCRIPT..."
		bash -c $PRE_TEST_SCRIPT
	fi

	echo "Starting integration tests..."
	python3 -m integrationtests

	if [[ -z "$AUTOTEST" ]]; then
		echo "Press enter to continue:"
		read
		echo "Continuing..."
	fi

	# Sleep very long to make sure all napalm jobs are finished?
	# TODO add some verification-steps here?
	sleep 10
	echo "Gathering coverage reports from integration tests:"
	MULE_PID="$($COMPOSE_COMMAND logs cnaas_api | awk '/spawned uWSGI mule/{print $6}' | egrep -o "[0-9]+" | tail -n1)"
	echo "Found mule at pid $MULE_PID"
	# Allow for code coverage files to be saved
	$COMPOSE_COMMAND exec -u root -T cnaas_api chown -R www-data:www-data /opt/cnaas/venv/cnaas-nms/src/
	curl -m 5 -ks -H "Authorization: Bearer $JWT_AUTH_TOKEN" "https://localhost/api/v1.0/system/shutdown" -d "{}" -X POST -H "Content-Type: application/json"
	sleep 3

	echo "Starting unit tests..."
	$COMPOSE_COMMAND exec -u www-data -T cnaas_api /opt/cnaas/pytest.sh
	echo "Try to generate coverage report:"
	if [[ -z "$AUTOTEST" ]]; then
		read -p "Do you want to upload coverage report to codecov.io? [y/N]" ans
		case $ans in
			[Yy]* ) $COMPOSE_COMMAND exec -u www-data -T cnaas_api /opt/cnaas/coverage.sh ;;
			* ) echo "Not uploading coverage report" ;;
		esac
	else
		$COMPOSE_COMMAND exec -u www-data -T cnaas_api /opt/cnaas/coverage.sh
	fi

	$COMPOSE_COMMAND logs cnaas_dhcpd
	$COMPOSE_COMMAND logs cnaas_api

	$COMPOSE_COMMAND down
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
	start_docker_environment
	setup_test_utilities
	wait_for_api
	start_integration_tests
fi

