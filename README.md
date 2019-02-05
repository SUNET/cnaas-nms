# CNaaS-NMS

Campus Network-as-a-service Network Management System

## Requirements

python3.7 or later
requirements.txt

## Installation

python3 -m pip install -r requirements.txt

cp etc/db_config.yml.sample /etc/cnaas-nms/db_config.py

## Test

cd src/

python3 -m cnaas_nms.api.tests.test_api

python3 -m cnaas_nms.confpush.tests.test_get

## License

Copyright (c) 2019, SUNET (BSD 2-clause license)

See LICENSE.txt for more info.
