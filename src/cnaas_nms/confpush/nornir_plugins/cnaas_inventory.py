from nornir.core.deserializer.inventory import Inventory

from cnaas_nms.cmdb.device import Device
import cnaas_nms.cmdb.session

class CnaasInventory(Inventory):
    def __init__(self, **kwargs):
        hosts = {}
        with cnaas_nms.cmdb.session.session_scope() as session:
            for instance in session.query(Device):
                hosts[instance.hostname] = {
                    'data': {
                        'platform': instance.platform
                    },
                    'groups': []
                }
        groups = {
            'global': {
                'data': {
                    'k': 'v'
                }
            }
        }
        defaults = {'data': {'k': 'v'} }
        super().__init__(hosts=hosts, groups=groups, defaults=defaults, **kwargs)


