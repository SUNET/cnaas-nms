[![Documentation Status](https://readthedocs.org/projects/cnaas-nms/badge/?version=latest)](https://cnaas-nms.readthedocs.io/en/latest/?badge=latest) [![codecov](https://codecov.io/gh/SUNET/cnaas-nms/branch/master/graph/badge.svg)](https://codecov.io/gh/SUNET/cnaas-nms) [![Python 3.7](https://img.shields.io/badge/python-3.7-blue.svg)](https://www.python.org/downloads/release/python-370/)

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

1. python3.7 or later
1. install requirements.txt
1. SQL database and MongoDB

## Installation

Create virtualenv and activate the environment

```
python3 -m pip install -r requirements.txt
cp etc/db_config.yml.sample /etc/cnaas-nms/db_config.py
```

## Test

```
cd src/
python3 -m cnaas_nms.api.tests.test_api
python3 -m cnaas_nms.confpush.tests.test_get
```

## License

Copyright (c) 2019, SUNET (BSD 2-clause license)

See LICENSE.txt for more info.
