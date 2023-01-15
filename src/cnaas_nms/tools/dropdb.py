#!/usr/bin/env python3
# flake8: noqa

import sys

from sqlalchemy import create_engine

from cnaas_nms.app_settings import app_settings

engine = create_engine(app_settings.POSTGRES_DSN)

connection = engine.connect()

from cnaas_nms.db.base import Base
from cnaas_nms.db.device import Device
from cnaas_nms.db.site import Site

print(Device.__table__)
print(Site.__table__)

print("Do you really want to drop ALL tables? (yes/NO): ")
ans = input()
if ans.lower() != "yes":
    sys.exit(0)


print(Base.metadata.drop_all(engine))
