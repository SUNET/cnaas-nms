#!/usr/bin/env python3

import yaml
from cnaas_nms.cmdb.session import session_scope

from cnaas_nms.cmdb.site import Site

with session_scope() as session:
    for site_instance in session.query(Site).order_by(Site.id):
        print(site_instance.id, site_instance.description)

