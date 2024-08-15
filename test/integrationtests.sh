#!/bin/bash -e

pushd .
cd ../docker/

export GITREPO_TEMPLATES="git://gitops.sunet.se/cnaas-lab-templates"
export GITREPO_SETTINGS="git://gitops.sunet.se/cnaas-lab-settings"
export GITREPO_ETC="https://github.com/indy-independence/cnaas-nms-lab-etc.git"
export USERNAME_DHCP_BOOT="admin"
export PASSWORD_DHCP_BOOT="abc123abc123"
export USERNAME_DISCOVERED="admin"
export PASSWORD_DISCOVERED="abc123abc123"
export USERNAME_INIT="admin"
export PASSWORD_INIT="abc123abc123"
export USERNAME_MANAGED="admin"
export PASSWORD_MANAGED="abc123abc123"
export COVERAGE=1
export PYTEST_POSTGRES_EXTERNAL=1
export PYTEST_REDIS_EXTERNAL=1
export PYTEST_SETTINGS_CLONED=1
export PYTEST_TEMPLATES_CLONED=1
export OIDC_ENABLED=0
export PERMISSIONS_DISABLED=1
export JWT_AUTH_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiJ9.eyJpYXQiOjE1NzEwNTk2MTgsIm5iZiI6MTU3MTA1OTYxOCwianRpIjoiNTQ2MDk2YTUtZTNmOS00NzFlLWE2NTctZWFlYTZkNzA4NmVhIiwic3ViIjoiYWRtaW4iLCJmcmVzaCI6ZmFsc2UsInR5cGUiOiJhY2Nlc3MifQ.Sfffg9oZg_Kmoq7Oe8IoTcbuagpP6nuUXOQzqJpgDfqDq_GM_4zGzt7XxByD4G0q8g4gZGHQnV14TpDer2hJXw"
export JWT_SECRET_KEY="integrationtestkey"

# select docker compose v 1 or 2
set +e
docker compose > /dev/null 2>&1
if [ $? -eq 1 ]
then
	echo "detected docker-compose v1"
	COMPOSE_COMMAND="docker-compose"
else
	echo "detected docker compose v2"
	COMPOSE_COMMAND="docker compose"
	COMPOSE_COMPATIBILITY=1
fi

$COMPOSE_COMMAND down -t 3

if docker volume ls | egrep -q "cnaas-postgres-data$"
then
	if [ -z "$AUTOTEST" ]
	then
		read -p "Do you want to continue and reset existing SQL database? [y/N]" ans
		case $ans in
			[Yy]* ) docker volume rm cnaas-postgres-data;;
			* ) exit 1;;
		esac
	else
		docker volume rm cnaas-postgres-data
	fi
fi

on_exit () {
    docker logs docker_cnaas_dhcpd_1
    docker logs docker_cnaas_api_1
    echo "Integrationtests exited (on_exit)"
}

on_err () {
    docker logs -n 100 docker_cnaas_api_1
}

trap on_exit EXIT
trap on_err ERR

docker volume create cnaas-templates
docker volume create cnaas-settings
docker volume create cnaas-postgres-data
docker volume create cnaas-jwtcert
docker volume create cnaas-cacert

set -e

$COMPOSE_COMMAND up -d

docker cp ./jwt-cert/public.pem docker_cnaas_api_1:/opt/cnaas/jwtcert/public.pem
$COMPOSE_COMMAND exec -u root -T cnaas_api /bin/chown -R www-data:www-data /opt/cnaas/jwtcert/
$COMPOSE_COMMAND exec -u root -T cnaas_api /opt/cnaas/createca.sh

sleep 5

curl --connect-timeout 2 --max-time 2 --retry 10 --retry-delay 0 --retry-max-time 60 -ks "https://localhost/api/v1.0/system/version"

# optional copy and restart
$COMPOSE_COMMAND exec -u root -T cnaas_api /bin/mv /opt/cnaas/venv/cnaas-nms/src/ /opt/cnaas/venv/cnaas-nms/src-bundled
docker cp ../src docker_cnaas_api_1:/opt/cnaas/venv/cnaas-nms/src
$COMPOSE_COMMAND exec -u root -T cnaas_api /bin/chown -R www-data:www-data /opt/cnaas/venv/cnaas-nms/src/
$COMPOSE_COMMAND exec -u root -T cnaas_api /usr/bin/killall uwsgi
#

if [ ! -z "$PRE_TEST_SCRIPT" ]
then
	if [ -x "$PRE_TEST_SCRIPT" ]
	then
		echo "Running PRE_TEST_SCRIPT..."
		bash -c $PRE_TEST_SCRIPT
	fi
fi

# go back to test dir
popd

#wait for port 5000
#retry refresh templates 100 times until success

echo "Starting integration tests..."
python3 -m integrationtests

set +e

if [ -z "$AUTOTEST" ]
then
	echo "Press enter to continue:"
	read
	echo "Continuing..."
fi

#coverage
# workaround to trigger coverage save
cd ../docker/
# Sleep very long to make sure all napalm jobs are finished?
sleep 120
echo "Gathering coverage reports from integration tests:"
MULE_PID="`docker logs docker_cnaas_api_1 | awk '/spawned uWSGI mule/{print $6}' | egrep -o "[0-9]+" | tail -n1`"
echo "Found mule at pid $MULE_PID"
# Allow for code coverage files to be saved
$COMPOSE_COMMAND exec -u root -T cnaas_api chown -R www-data:www-data /opt/cnaas/venv/cnaas-nms/src/
curl -ks -H "Authorization: Bearer $JWT_AUTH_TOKEN" "https://localhost/api/v1.0/system/shutdown" -d "{}" -X POST -H "Content-Type: application/json"
sleep 3

echo "Starting unit tests..."
$COMPOSE_COMMAND exec -u www-data -T cnaas_api /opt/cnaas/pytest.sh
echo "Try to generate coverage report:"
if [ -z "$AUTOTEST" ]
then
	read -p "Do you want to upload coverage report to codecov.io? [y/N]" ans
	case $ans in
		[Yy]* ) $COMPOSE_COMMAND exec -u www-data -T cnaas_api /opt/cnaas/coverage.sh;;
		* ) echo "Not uploading coverage report";;
	esac
else
	$COMPOSE_COMMAND exec -u www-data -T cnaas_api /opt/cnaas/coverage.sh
fi

docker logs docker_cnaas_dhcpd_1
docker logs docker_cnaas_api_1

$COMPOSE_COMMAND down
