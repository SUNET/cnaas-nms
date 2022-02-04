import ipaddress
import os

from nornir.core.inventory import ConnectionOptions, Defaults, Group, Groups, Host, Hosts, Inventory, ParentGroups

import cnaas_nms.db.session
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.settings import get_groups
from cnaas_nms.tools.pki import ssl_context


class CnaasInventory:
    @staticmethod
    def _get_credentials(devicestate):
        if devicestate == 'UNKNOWN':
            return None, None
        elif devicestate in ['UNMANAGED', 'MANAGED_NOIF']:
            env_var = 'MANAGED'
        elif devicestate == 'PRE_CONFIGURED':
            env_var = 'DHCP_BOOT'
        else:
            env_var = devicestate

        try:
            username = os.environ['USERNAME_' + env_var]
            password = os.environ['PASSWORD_' + env_var]
        except Exception:
            raise ValueError('Could not find credentials for state ' + devicestate)
        return username, password

    @staticmethod
    def _get_management_ip(management_ip, dhcp_ip):
        if issubclass(management_ip.__class__, ipaddress.IPv4Address):
            return str(management_ip)
        elif issubclass(dhcp_ip.__class__, ipaddress.IPv4Address):
            return str(dhcp_ip)
        else:
            return None

    def load(self) -> Inventory:
        defaults = Defaults(
            connection_options={
                "napalm": ConnectionOptions(extras={
                    "optional_args": {
                        # args to eAPI HttpsEapiConnection for EOS
                        "enforce_verification": True,
                        "context": ssl_context
                    }
                })
            }
        )
        insecure_device_states = [
            DeviceState.INIT,
            DeviceState.DHCP_BOOT,
            DeviceState.PRE_CONFIGURED,
            DeviceState.DISCOVERED
        ]
        insecure_connection_options = {
            "napalm": ConnectionOptions(extras={
                "optional_args": {"enforce_verification": False}
            })
        }

        groups = Groups()
        for device_type in list(DeviceType.__members__):
            group_name = 'T_'+device_type
            groups[group_name] = Group(name=group_name, defaults=defaults)
        for device_state in list(DeviceState.__members__):
            username, password = self._get_credentials(device_state)
            group_name = 'S_'+device_state
            groups[group_name] = Group(
                name=group_name, username=username, password=password, defaults=defaults)
        for group_name in get_groups():
            groups[group_name] = Group(name=group_name, defaults=defaults)

        hosts = Hosts()
        with cnaas_nms.db.session.sqla_session() as session:
            instance: Device
            for instance in session.query(Device):
                hostname = self._get_management_ip(instance.management_ip,
                                                   instance.dhcp_ip)
                port = None
                if instance.port and isinstance(instance.port, int):
                    port = instance.port
                host_groups = [
                    'T_' + instance.device_type.name,
                    'S_' + instance.state.name
                ]
                for member_group in get_groups(instance.hostname):
                    host_groups.append(member_group)

                if instance.state in insecure_device_states:
                    host_connection_options = insecure_connection_options
                else:
                    host_connection_options = None
                hosts[instance.hostname] = Host(
                    name=instance.hostname,
                    hostname=hostname,
                    platform=instance.platform,
                    groups=ParentGroups(groups[g] for g in host_groups),
                    port=port,
                    data={
                        'synchronized': instance.synchronized,
                        'managed': (True if instance.state == DeviceState.MANAGED else False)
                    },
                    connection_options=host_connection_options,
                    defaults=defaults
                )

        return Inventory(hosts=hosts, groups=groups, defaults=defaults)
