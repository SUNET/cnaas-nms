from typing import Optional
from ipaddress import IPv4Interface
import os
import yaml

from nornir.plugins.tasks import networking, text
from nornir.plugins.functions.text import print_result
from nornir.core.filter import F

import cnaas_nms.db.helper
import cnaas_nms.confpush.nornir_helper
from cnaas_nms.db.session import sqla_session
from cnaas_nms.confpush.get import get_uplinks, get_running_config_hash
from cnaas_nms.tools.log import get_logger
from cnaas_nms.db.settings import get_settings
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.db.git import RepoStructureException
from cnaas_nms.confpush.nornir_helper import NornirJobResult
from cnaas_nms.scheduler.wrapper import job_wrapper

logger = get_logger()


def push_sync_device(task, dry_run: bool = True):
    hostname = task.host.name
    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
        mgmt_ip = dev.management_ip
        devtype: DeviceType = dev.device_type
        if isinstance(dev.platform, str):
            platform: str = dev.platform
        else:
            raise ValueError("Unknown platform: {}".format(dev.platform))

        neighbor_hostnames = dev.get_uplink_peers(session)
        mgmtdomain = cnaas_nms.db.helper.find_mgmtdomain(session, neighbor_hostnames)
        if not mgmtdomain:
            raise Exception(
                "Could not find appropriate management domain for uplink peer devices: {}".format(
                    neighbor_hostnames))

        if not mgmt_ip:
            raise Exception("Could not find management IP for device {}".format(hostname))
        mgmt_gw_ipif = IPv4Interface(mgmtdomain.ipv4_gw)

        intfs = session.query(Interface).filter(Interface.device == dev).all()
        uplinks = []
        access_auto = []
        intf: Interface
        for intf in intfs:
            if intf.configtype == InterfaceConfigType.ACCESS_AUTO:
                access_auto.append({'ifname': intf.name})
            elif intf.configtype == InterfaceConfigType.ACCESS_UPLINK:
                uplinks.append({'ifname': intf.name})
        device_variables = {
            'mgmt_ipif': str(IPv4Interface('{}/{}'.format(mgmt_ip, mgmt_gw_ipif.network.prefixlen))),
            'mgmt_ip': str(mgmt_ip),
            'mgmt_prefixlen': int(mgmt_gw_ipif.network.prefixlen),
            'uplinks': uplinks,
            'access_auto': access_auto,
            'mgmt_vlan_id': mgmtdomain.vlan,
            'mgmt_gw': mgmt_gw_ipif.ip
        }

    settings, settings_origin = get_settings(hostname, devtype)
    # Merge dicts
    template_vars = {**device_variables, **settings}

    logger.debug("Synchronize device config for host: {}".format(task.host.name))

    with open('/etc/cnaas-nms/repository.yml', 'r') as db_file:
        repo_config = yaml.safe_load(db_file)
        local_repo_path = repo_config['templates_local']

    mapfile = os.path.join(local_repo_path, platform, 'mapping.yml')
    if not os.path.isfile(mapfile):
        raise RepoStructureException("File {} not found in template repo".format(mapfile))
    with open(mapfile, 'r') as f:
        mapping = yaml.safe_load(f)
        template = mapping[devtype.name]['entrypoint']

    r = task.run(task=text.template_file,
                 name="Generate device config",
                 template=template,
                 path=f"{local_repo_path}/{task.host.platform}",
                 **template_vars)

    # TODO: Handle template not found, variables not defined
    # jinja2.exceptions.UndefinedError

    task.host["config"] = r.result

    task.run(task=networking.napalm_configure,
             name="Sync device config",
             replace=True,
             configuration=task.host["config"],
             dry_run=dry_run
             )


@job_wrapper
def sync_devices(hostname: Optional[str] = None, device_type: Optional[DeviceType] = None,
                 dry_run: bool = True, force: bool = False) -> NornirJobResult:
    """Synchronize devices to their respective templates. If no arguments
    are specified then synchronize all devices that are currently out
    of sync.

    Args:
        hostname: Specify a single host by hostname to synchronize
        device_type: Specify a device type to synchronize

    Returns:
        NornirJobResult
    """
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    if hostname:
        nr_filtered = nr.filter(name=hostname).filter(managed=True)
    elif device_type:
        nr_filtered = nr.filter(F(groups__contains='T_'+device_type.name))  # device type
    else:
        nr_filtered = nr.filter(synchronized=False).filter(managed=True)  # all unsynchronized devices

    device_list = list(nr_filtered.inventory.hosts.keys())
    logger.info("Device(s) selected for synchronization: {}".format(
        device_list
    ))

    for device in device_list:
        alterned_devices = []
        stored_config_hash = Device.get_config_hash(device)
        if stored_config_hash is None:
            continue
        current_config_hash = get_running_config_hash(device)
        if current_config_hash is None:
            raise Exception('Failed to get configuration hash')
        if stored_config_hash != current_config_hash:
            logger.info("Device {} configuration is altered outside of CNaaS!".format(device))
            alterned_devices.append(device)
    if alterned_devices != [] and force is False:
        raise Exception('Configuration for {} is altered outside of CNaaS'.format(', '.join(alterned_devices)))

    try:
        nrresult = nr_filtered.run(task=push_sync_device, dry_run=dry_run)
        print_result(nrresult)
    except Exception as e:
        logger.exception("Exception while synchronizing devices: {}".format(str(e)))
        return NornirJobResult(nrresult=nrresult)

    failed_hosts = list(nrresult.failed_hosts.keys())

    if not dry_run:
        for key in nrresult.keys():
            if key in failed_hosts:
                continue
            new_config_hash = get_running_config_hash(key)
            if new_config_hash is None:
                raise Exception('Failed to get configuration hash')
            Device.set_config_hash(key, get_running_config_hash(key))

        with sqla_session() as session:
            for hostname in device_list:
                if hostname in failed_hosts:
                    logger.error("Synchronization of device '{}' failed".format(hostname))
                    continue
                dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
                dev.synchronized = True

    if nrresult.failed:
        logger.error("Not all devices were successfully synchronized")

    return NornirJobResult(nrresult=nrresult)
