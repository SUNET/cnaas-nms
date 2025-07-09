[![Documentation Status](https://readthedocs.org/projects/cnaas-nms/badge/?version=latest)](https://cnaas-nms.readthedocs.io/en/latest/?badge=latest) [![codecov](https://codecov.io/gh/SUNET/cnaas-nms/branch/master/graph/badge.svg)](https://codecov.io/gh/SUNET/cnaas-nms) [![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)

# CNaaS-NMS

Campus Network-as-a-Service - Network Management System. Software to automate management of a campus network (LAN). This is an open source software developed as part of SUNETs managed service.

Planned features:
1. Zero-touch provisioning of switches
1. Automation of common changes for campus LAN
1. Automated procedure for firmware upgrades
1. Multi-vendor support

[Documentation](https://cnaas-nms.readthedocs.io/)

## Components

![CNaaS component architecture](cnaas-components-20190408.png?raw=true)

## Requirements

Docker and docker-compose or:

1. python3.7 or later
1. install requirements.txt
1. SQL database, Redis

## Installation

Install docker and docker-compose and run: docker-compose build -f docker/docker-compose.yaml

Or install locally by creating a virtualenv and activate the environment, then:

```
python3 -m pip install -r requirements.txt
cp etc/db_config.yml.sample /etc/cnaas-nms/db_config.yml
```

Edit db_config.yml to point to your SQL and redis database.

## Test

```
cd src/
pytest
```

two marks can be used for pytest `integration` and `equipment`, so tests a subset of all tests can be run with eg

```
pytest -m "not integration" -m "not equipment"
```

By default, **pytest-docker** will use *docker/docker-compose_pytest.yaml* to spin up PostgreSQL and Redis. To use another docker compose file, use the environment variable `DOCKER_COMPOSE_FILE` can be set to names of docker-compose files under docker/ folder.

To run some tests with another container, eg

```
DOCKER_COMPOSE_FILE="docker-compose_test.yaml" pytest -m "not equipment"
```

If the tests should not spin up any containers at all, set the environment variable `EXTERNAL_TEST_CONTAINERS`, eg

```
EXTERNAL_TEST_CONTAINERS=1 pytest -m "not equipment"
```

## Authorization

Currently we can use two styles for the authorization. We can use the original style or use OIDC style. For OIDC we need to define some env variables or add a auth_config.yaml in the config. The needed variables are: OIDC_CONF_WELL_KNOWN_URL, OIDC_CLIENT_SECRET, OIDC_CLIENT_ID, FRONTEND_CALLBACK_URL and OIDC_ENABLED. To use the OIDC style the last variable needs to be set to true.

## License

Copyright (c) 2019 - 2020, SUNET (BSD 2-clause license)

See LICENSE.txt for more info.
