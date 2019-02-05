#!/usr/bin/env python3

import sys
import yaml

with open('database.yml', 'r') as db_file:
    db_data = yaml.load(db_file)

print(db_data)
conn_str = (
    f"postgresql://{db_data['username']}:{db_data['password']}@"
    f"{db_data['hostname']}:{db_data['port']}"
)

from sqlalchemy import create_engine

engine = create_engine(conn_str)

connection = engine.connect()

from cmdb.base import Base
from cmdb.device import Device, DeviceType, DeviceState
from cmdb.site import Site

print(Device.__table__)
print(Site.__table__)

print("Do you really want to drop ALL tables? (yes/NO): ")
ans = input()
if ans.lower() != 'yes':
    sys.exit(0)


print(Base.metadata.drop_all(engine))

