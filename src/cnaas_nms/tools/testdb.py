#!/usr/bin/env python3

import yaml
from cnaas_nms.cmdb.session import session_scope

from cnaas_nms.cmdb.site import Site
from cnaas_nms.cmdb.device import Device

with session_scope() as session:
    for site_instance in session.query(Site).order_by(Site.id):
        print(site_instance.id, site_instance.description)
    for device_instance in session.query(Device).order_by(Device.id):
        print(device_instance.hostname, device_instance.ztp_mac, device_instance.serial)

