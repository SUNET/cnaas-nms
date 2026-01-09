[![Documentation Status](https://readthedocs.org/projects/cnaas-nms/badge/?version=latest)](https://cnaas-nms.readthedocs.io/en/latest/?badge=latest) [![codecov](https://codecov.io/gh/SUNET/cnaas-nms/branch/master/graph/badge.svg)](https://codecov.io/gh/SUNET/cnaas-nms) [![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)

# CNaaS-NMS

Campus Network-as-a-Service - Network Management System. Software to automate management of a campus network (LAN). This is an open source software developed as part of SUNETs managed service.

Planned features:
1. Zero-touch provisioning of switches
2. Automation of common changes for campus LAN
3. Automated procedure for firmware upgrades
4. Multi-vendor support

[Documentation](https://cnaas-nms.readthedocs.io/)

## Components

![CNaaS component architecture](cnaas-components-20190408.png?raw=true)

## Dependencies

Dependencies are specified in `[dependency-groups]` in _pyproject.toml_. The are curently three groups

- `dependencies`
- `dev`
- `docs`

dependencies from each group can be installed with

```sh
pip install --group <group>
```

**Note**: requires pip 25.1 or later.

## Requirements

Docker and docker compose or:

1. python3.11 or later
2. `pip install --group dependencies` (requires pip 25.1 or later)
3. SQL database, Redis

## Installation

### Docker

Install docker with docker compose and run: `docker compose build -f docker/docker-compose.yaml`

### Venv

Install locally by creating a virtualenv and activate the environment, then:

```
python3 -m pip install --group dependencies
cp etc/db_config.yml.sample /etc/cnaas-nms/db_config.yml
```

Edit db_config.yml to point to your SQL and redis database.

## Test

```
cd src/
pytest
```

Two marks can be used for pytest: `integration` and `equipment`, that can be be used to do a subset of all tests. Eg

```
pytest -m "not integration and not equipment"
```

Note that `and` must be used to apply filters at the same time.

If the tests should not spin up any containers at all, set the environment variable `EXTERNAL_TEST_CONTAINERS`, eg

```
EXTERNAL_TEST_CONTAINERS=1 pytest -m "not equipment"
```

## Authorization

Currently we can use two styles for the authorization. We can use the original style or use OIDC style. For OIDC we need to define some env variables or add a auth_config.yaml in the config. The needed variables are: OIDC_CONF_WELL_KNOWN_URL, OIDC_CLIENT_SECRET, OIDC_CLIENT_ID, FRONTEND_CALLBACK_URL and OIDC_ENABLED. To use the OIDC style the last variable needs to be set to true.

## License

Copyright (c) 2019 - 2020, SUNET (BSD 2-clause license)

See LICENSE.txt for more info.
