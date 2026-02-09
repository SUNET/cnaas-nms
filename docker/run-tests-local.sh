#!/bin/bash
# Run tests locally in Docker containers
set -e

cd "$(dirname "$0")"

# Check if containers are running
if ! docker compose -f docker-compose_test.yaml ps --status running | grep -q cnaas_api; then
    echo "Error: Containers not running. Start them with:" >&2
    echo "  docker compose -f docker-compose_test.yaml -f docker-compose.test-local.yaml up -d" >&2
    exit 1
fi

# Install JWT cert if missing
if ! docker compose -f docker-compose_test.yaml exec -T cnaas_api test -f /opt/cnaas/jwtcert/public.pem; then
    echo "Installing JWT certificate..."
    docker cp ./jwt-cert/public.pem "$(docker compose -f docker-compose_test.yaml ps -q cnaas_api)":/opt/cnaas/jwtcert/public.pem
    docker compose -f docker-compose_test.yaml exec -u root -T cnaas_api chown -R www-data:www-data /opt/cnaas/jwtcert/
fi

# Create CA if missing
docker compose -f docker-compose_test.yaml exec -u root -T cnaas_api /opt/cnaas/createca.sh 2>/dev/null || true

# Run tests
echo "Running tests..."
docker compose -f docker-compose_test.yaml exec \
    -e EXTERNAL_TEST_CONTAINERS=1 \
    -e NO_EQUIPMENTTEST=1 \
    -u www-data \
    -T cnaas_api \
    /opt/cnaas/pytest.sh "$@"
