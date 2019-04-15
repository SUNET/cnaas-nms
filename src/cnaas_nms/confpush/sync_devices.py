from ipaddress import IPv4Interface

from nornir.plugins.tasks import networking, text
from nornir.plugins.functions.text import print_result

import cnaas_nms.db.helper
import cnaas_nms.confpush.nornir_helper
from cnaas_nms.db.session import sqla_session
from cnaas_nms.confpush.get import get_uplinks
from cnaas_nms.tools.log import get_logger
from cnaas_nms.db.settings import get_settings
from cnaas_nms.db.device import Device, DeviceState, DeviceType, DeviceStateException

logger = get_logger()


def push_sync_device(task, dry_run: bool = True):
    hostname = task.host.name
    with sqla_session() as session:
        uplinks, neighbor_hostnames = get_uplinks(session, hostname)

        mgmtdomain = cnaas_nms.db.helper.find_mgmtdomain(session, neighbor_hostnames)
        if not mgmtdomain:
            raise Exception(
                "Could not find appropriate management domain for uplink peer devices: {}".format(
                    neighbor_hostnames))
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
        mgmt_ip = dev.management_ip

        if not mgmt_ip:
            raise Exception("Could not find free management IP for management domain {}".format(
                mgmtdomain.id))
        mgmt_gw_ipif = IPv4Interface(mgmtdomain.ipv4_gw)
        device_variables = {
            'mgmt_ip': str(IPv4Interface('{}/{}'.format(mgmt_ip, mgmt_gw_ipif.network.prefixlen))),
            'uplinks': uplinks,
            'mgmt_vlan_id': mgmtdomain.vlan,
            'mgmt_gw': mgmt_gw_ipif.ip
        }

    settings = get_settings(hostname)
    # Merge dicts
    template_vars = {**device_variables, **settings}

    logger.debug("Synchronize device config for host: {}".format(task.host.name))

    r = task.run(task=text.template_file,
                 name="Sync device",
                 template="managed-full.j2",
                 path=f"../templates/{task.host.platform}",
                 **template_vars)

    # TODO: Handle template not found, variables not defined

    task.host["config"] = r.result

    task.run(task=networking.napalm_configure,
             name="Push base management config",
             replace=True,
             configuration=task.host["config"],
             dry_run=dry_run
             )


def sync_device(hostname: str):
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)

    # step2. push management config
    try:
        nrresult = nr_filtered.run(task=push_sync_device, dry_run = True)
        print_result(nrresult)
    except Exception as e:
        import pdb
        pdb.set_trace()

