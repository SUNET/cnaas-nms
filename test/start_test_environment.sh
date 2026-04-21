#!/bin/bash -e

pushd .
cd ../docker/

export GITREPO_TEMPLATES="https://github.com/SUNET/cnaas-integrationtest-templates.git"
export GITREPO_SETTINGS="https://github.com/SUNET/cnaas-integrationtest-settings.git"
export GITREPO_ETC="https://github.com/indy-independence/cnaas-nms-lab-etc.git"
export USERNAME_DHCP_BOOT="admin"
export PASSWORD_DHCP_BOOT="abc123abc123"
export USERNAME_DISCOVERED="admin"
export PASSWORD_DISCOVERED="abc123abc123"
export USERNAME_INIT="admin"
export PASSWORD_INIT="abc123abc123"
export USERNAME_MANAGED="admin"
export PASSWORD_MANAGED="abc123abc123"
export EXTERNAL_TEST_CONTAINERS=1
export PYTEST_SETTINGS_CLONED=1
export PYTEST_TEMPLATES_CLONED=1
export OIDC_ENABLED=0
export PERMISSIONS_DISABLED=1
export JWT_AUTH_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiJ9.eyJpYXQiOjE1NzEwNTk2MTgsIm5iZiI6MTU3MTA1OTYxOCwianRpIjoiNTQ2MDk2YTUtZTNmOS00NzFlLWE2NTctZWFlYTZkNzA4NmVhIiwic3ViIjoiYWRtaW4iLCJmcmVzaCI6ZmFsc2UsInR5cGUiOiJhY2Nlc3MifQ.Sfffg9oZg_Kmoq7Oe8IoTcbuagpP6nuUXOQzqJpgDfqDq_GM_4zGzt7XxByD4G0q8g4gZGHQnV14TpDer2hJXw"
export JWT_SECRET_KEY="integrationtestkey"

# select docker compose v 1 or 2
set +e

docker compose >/dev/null 2>&1
if [[ $? -eq 1 ]]; then
	echo "detected docker-compose v1"
	COMPOSE_COMMAND="docker-compose"
else
	echo "detected docker compose v2"
	COMPOSE_COMMAND="docker compose"
	export COMPOSE_COMPATIBILITY=1
fi

$COMPOSE_COMMAND down -t 3

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

set -e

$COMPOSE_COMMAND up -d

$COMPOSE_COMMAND cp ./jwt-cert/public.pem cnaas_api:/opt/cnaas/jwtcert/public.pem

$COMPOSE_COMMAND exec -u root -T cnaas_api /bin/chown -R www-data:www-data /opt/cnaas/jwtcert/

$COMPOSE_COMMAND exec -u root -T cnaas_api /opt/cnaas/createca.sh

echo "Waiting for API to become ready..."

for i in {1..60}; do
    if curl -ks https://localhost/api/v1.0/system/version >/dev/null 2>&1; then
		# Show version
		curl -ks https://localhost/api/v1.0/system/version
        break
    fi
done

# go back to test dir
popd

echo "Seeding test-environment"

python3 -c "
from integrationtests import GetTests
tests = GetTests()
tests.test_00_sync()
tests.test_01_init_dist()
"

echo "Test environment is now initialized"
