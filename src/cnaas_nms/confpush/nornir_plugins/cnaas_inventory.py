from nornir.core.deserializer.inventory import Inventory

from cnaas_nms.cmdb.device import Device, DeviceType, DeviceState
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
                    'groups': [
                        'T_'+instance.device_type.name,
                        'S_'+instance.state.name
                    ]
                }
        groups = {
            'global': {
                'data': {
                    'k': 'v'
                }
            }
        }
        for device_type in list(DeviceType.__members__):
            groups['T_'+device_type] = {}
        for device_type in list(DeviceState.__members__):
            groups['S_'+device_type] = {}
        defaults = {'data': {'k': 'v'} }
        super().__init__(hosts=hosts, groups=groups, defaults=defaults, **kwargs)


