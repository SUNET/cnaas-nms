#!/bin/bash
# Run tests locally: unit tests first, then integration tests
set -e

cd "$(dirname "$0")/.."

TEST_DATA_DIR=".test-data"
TEMPLATES_DIR="$TEST_DATA_DIR/templates"
SETTINGS_DIR="$TEST_DATA_DIR/settings"

TEMPLATES_REPO="https://github.com/SUNET/cnaas-integrationtest-templates.git"
SETTINGS_REPO="https://github.com/SUNET/cnaas-integrationtest-settings.git"

# Provision test data (clone once, reuse)
provision_test_data() {
  mkdir -p "$TEST_DATA_DIR"

  if [ ! -d "$TEMPLATES_DIR/.git" ]; then
    echo "Cloning templates..."
    git clone --depth 1 --no-single-branch "$TEMPLATES_REPO" "$TEMPLATES_DIR"
  fi

  if [ ! -d "$SETTINGS_DIR/.git" ]; then
    echo "Cloning settings..."
    git clone --depth 1 "$SETTINGS_REPO" "$SETTINGS_DIR"
  fi
}

# Start databases if not running
if ! docker compose -f docker/docker-compose_pytest.yaml ps --status running | grep -q cnaas_postgres; then
  echo "Starting test databases..."
  docker compose -f docker/docker-compose_pytest.yaml up -d
  echo "Waiting for databases to be ready..."
  sleep 10
fi

# Ensure pytest is available
if ! command -v pytest &>/dev/null; then
  echo "Error: pytest not found. Install with: pip install . --group dev" >&2
  exit 1
fi

# Provision templates
provision_test_data

# Set environment
export EXTERNAL_TEST_CONTAINERS=1
export JWT_SECRET_KEY=unittestsharedsecret
export PERMISSIONS_DISABLED=True
TEMPLATES_LOCAL="$(pwd)/$TEMPLATES_DIR"
export TEMPLATES_LOCAL
SETTINGS_LOCAL="$(pwd)/$SETTINGS_DIR"
export SETTINGS_LOCAL

# Run unit tests first
echo "Running unit tests..."
pytest -vv --showlocals -m "not equipment and not integration" "$@"

# If unit tests pass, run integration tests
echo "Running integration tests..."
pytest -vv --showlocals -m "integration and not equipment" "$@"

echo "All tests passed!"
