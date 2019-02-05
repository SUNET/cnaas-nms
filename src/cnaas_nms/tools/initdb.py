#!/usr/bin/env python3

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

print(Base.metadata.create_all(engine))

t = Site()
t.description = 'default'

from sqlalchemy.orm import sessionmaker

Session = sessionmaker(bind=engine)

session = Session()

session.add(t)

print(session.new)

session.commit()


td = Device()
td.description = 'Test device!'
td.hostname = 'testdevice'
td.management_ip = '1.2.3.4'
td.platform = 'eos'
td.serial = ''
td.site = t
td.state = DeviceState.UNKNOWN
td.device_type = DeviceType.UNKNOWN

session.add(td)

print(session.new)

session.commit()
