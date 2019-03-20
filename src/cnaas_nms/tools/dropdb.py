#!/usr/bin/env python3

import sys
import yaml

with open('/etc/cnaas-nms/db_config.yml', 'r') as db_file:
    db_data = yaml.safe_load(db_file)

print(db_data)
conn_str = (
    f"postgresql://{db_data['username']}:{db_data['password']}@"
    f"{db_data['hostname']}:{db_data['port']}"
)

from sqlalchemy import create_engine

engine = create_engine(conn_str)

connection = engine.connect()

from cnaas_nms.db.base import Base
from cnaas_nms.db.device import Device, DeviceType, DeviceState
from cnaas_nms.db.site import Site

print(Device.__table__)
print(Site.__table__)

print("Do you really want to drop ALL tables? (yes/NO): ")
ans = input()
if ans.lower() != 'yes':
    sys.exit(0)


print(Base.metadata.drop_all(engine))

