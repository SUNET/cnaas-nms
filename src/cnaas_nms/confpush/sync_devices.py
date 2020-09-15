import os
import yaml
from typing import Optional, List
from ipaddress import IPv4Interface, IPv4Address
from statistics import median
from hashlib import sha256

from nornir.plugins.tasks import networking, text
from nornir.plugins.functions.text import print_result
from nornir.core.task import MultiResult

import cnaas_nms.db.helper
from cnaas_nms.confpush.nornir_helper import cnaas_init, inventory_selector
from cnaas_nms.db.session import sqla_session, redis_session
from cnaas_nms.confpush.get import calc_config_hash
from cnaas_nms.confpush.changescore import calculate_score
from cnaas_nms.tools.log import get_logger
from cnaas_nms.db.settings import get_settings
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.db.joblock import Joblock, JoblockError
from cnaas_nms.db.git import RepoStructureException
from cnaas_nms.confpush.nornir_helper import NornirJobResult
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.scheduler.thread_data import set_thread_data

from cnaas_nms.scheduler.scheduler import Scheduler
from nornir.plugins.tasks.networking import napalm_get


AUTOPUSH_MAX_SCORE = 10
PRIVATE_ASN_START = 4200000000


def generate_asn(ipv4_address: IPv4Address) -> Optional[int]:
    """Generate a unique private 4 byte AS number based on last two octets of
    an IPv4 address (infra_lo)"""
    return PRIVATE_ASN_START + (ipv4_address.packed[2]*256 + ipv4_address.packed[3])


def get_evpn_spines(session, settings: dict):
    logger = get_logger()
    device_hostnames = []
    for entry in settings['evpn_peers']:
        if 'hostname' in entry and Device.valid_hostname(entry['hostname']):
            device_hostnames.append(entry['hostname'])
        else:
            logger.error("Invalid entry specified in settings->evpn_peers, ignoring: {}".format(entry))
    ret = []
    for hostname in device_hostnames:
        dev = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if dev:
            ret.append(dev)
    return ret


def resolve_vlanid(vlan_name: str, vxlans: dict) -> Optional[int]:
    logger = get_logger()
    if type(vlan_name) == int:
        return int(vlan_name)
    if not isinstance(vlan_name, str):
        return None
    for vxlan_name, vxlan_data in vxlans.items():
        try:
            if vxlan_data['vlan_name'] == vlan_name:
                return int(vxlan_data['vlan_id'])
        except (KeyError, ValueError) as e:
            logger.error("Could not resolve VLAN ID for VLAN name {}: {}".format(vlan_name, str(e)))
            return None


def resolve_vlanid_list(vlan_name_list: List[str], vxlans: dict) -> List[int]:
    if not isinstance(vlan_name_list, list):
        return []
    ret = []
    for vlan_name in vlan_name_list:
        vlan_id = resolve_vlanid(vlan_name, vxlans)
        if vlan_id:
            ret.append(vlan_id)
    return ret


def get_mlag_vars(session, dev: Device) -> dict:
    ret = {
        'mlag_peer': False,
        'mlag_peer_hostname': None,
        'mlag_peer_low': None
    }
    mlag_peer: Device = dev.get_mlag_peer(session)
    if not mlag_peer:
        return ret
    ret['mlag_peer'] = True
    ret['mlag_peer_hostname'] = mlag_peer.hostname
    if dev.id < mlag_peer.id:
        ret['mlag_peer_low'] = True
    else:
        ret['mlag_peer_low'] = False
    return ret


def push_sync_device(task, dry_run: bool = True, generate_only: bool = False,
                     job_id: Optional[str] = None,
                     scheduled_by: Optional[str] = None):
    """
    Nornir task to generate config and push to device

    Args:
        task: nornir task, sent by nornir when doing .run()
        dry_run: Don't commit config to device, just do compare/diff
        generate_only: Only generate text config, don't try to commit or
                       even do dry_run compare to running config

    Returns:

    """
    set_thread_data(job_id)
    logger = get_logger()
    hostname = task.host.name
    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
        mgmt_ip = dev.management_ip
        infra_ip = dev.infra_ip
        if not mgmt_ip:
            raise Exception("Could not find management IP for device {}".format(hostname))
        devtype: DeviceType = dev.device_type
        if isinstance(dev.platform, str):
            platform: str = dev.platform
        else:
            raise ValueError("Unknown platform: {}".format(dev.platform))
        settings, settings_origin = get_settings(hostname, devtype, dev.model)
        device_variables = {
            'mgmt_ip': str(mgmt_ip),
            'device_model': dev.model,
            'device_os_version': dev.os_version
        }

        if devtype == DeviceType.ACCESS:
            mgmtdomain = cnaas_nms.db.helper.find_mgmtdomain_by_ip(session, dev.management_ip)
            if not mgmtdomain:
                raise Exception(
                    "Could not find appropriate management domain for management_ip: {}".
                    format(dev.management_ip))

            mgmt_gw_ipif = IPv4Interface(mgmtdomain.ipv4_gw)
            access_device_variables = {
                'mgmt_vlan_id': mgmtdomain.vlan,
                'mgmt_gw': str(mgmt_gw_ipif.ip),
                'mgmt_ipif': str(IPv4Interface('{}/{}'.format(mgmt_ip,
                                                              mgmt_gw_ipif.network.prefixlen))),
                'mgmt_prefixlen': int(mgmt_gw_ipif.network.prefixlen),
                'interfaces': []
            }
            intfs = session.query(Interface).filter(Interface.device == dev).all()
            intf: Interface
            for intf in intfs:
                untagged_vlan = None
                tagged_vlan_list = []
                intfdata = None
                if intf.data:
                    if 'untagged_vlan' in intf.data:
                        untagged_vlan = resolve_vlanid(intf.data['untagged_vlan'],
                                                       settings['vxlans'])
                    if 'tagged_vlan_list' in intf.data:
                        tagged_vlan_list = resolve_vlanid_list(intf.data['tagged_vlan_list'],
                                                               settings['vxlans'])
                    intfdata = dict(intf.data)
                access_device_variables['interfaces'].append({
                    'name': intf.name,
                    'ifclass': intf.configtype.name,
                    'untagged_vlan': untagged_vlan,
                    'tagged_vlan_list': tagged_vlan_list,
                    'data': intfdata
                })
            mlag_vars = get_mlag_vars(session, dev)
            device_variables = {**access_device_variables, **device_variables, **mlag_vars}
        elif devtype == DeviceType.DIST or devtype == DeviceType.CORE:
            asn = generate_asn(infra_ip)
            fabric_device_variables = {
                'mgmt_ipif': str(IPv4Interface('{}/32'.format(mgmt_ip))),
                'mgmt_prefixlen': 32,
                'infra_ipif': str(IPv4Interface('{}/32'.format(infra_ip))),
                'infra_ip': str(infra_ip),
                'interfaces': [],
                'bgp_ipv4_peers': [],
                'bgp_evpn_peers': [],
                'mgmtdomains': [],
                'asn': asn
            }
            ifname_peer_map = dev.get_linknet_localif_mapping(session)
            if 'interfaces' in settings and settings['interfaces']:
                for intf in settings['interfaces']:
                    try:
                        ifindexnum: int = Interface.interface_index_num(intf['name'])
                    except ValueError as e:
                        ifindexnum: int = 0
                    if 'ifclass' in intf and intf['ifclass'] == 'downlink':
                        data = {}
                        if intf['name'] in ifname_peer_map:
                            data['description'] = ifname_peer_map[intf['name']]
                        fabric_device_variables['interfaces'].append({
                            'name': intf['name'],
                            'ifclass': intf['ifclass'],
                            'indexnum': ifindexnum,
                            'data': data
                        })
                    elif 'ifclass' in intf and intf['ifclass'] == 'custom':
                        fabric_device_variables['interfaces'].append({
                            'name': intf['name'],
                            'ifclass': intf['ifclass'],
                            'config': intf['config'],
                            'indexnum': ifindexnum
                        })
            for mgmtdom in cnaas_nms.db.helper.get_all_mgmtdomains(session, hostname):
                fabric_device_variables['mgmtdomains'].append({
                    'id': mgmtdom.id,
                    'ipv4_gw': mgmtdom.ipv4_gw,
                    'vlan': mgmtdom.vlan,
                    'description': mgmtdom.description,
                    'esi_mac': mgmtdom.esi_mac
                })
            # find fabric neighbors
            fabric_links = []
            for neighbor_d in dev.get_neighbors(session):
                if neighbor_d.device_type == DeviceType.DIST or neighbor_d.device_type == DeviceType.CORE:
                    # TODO: support multiple links to the same neighbor?
                    local_if = dev.get_neighbor_local_ifname(session, neighbor_d)
                    local_ipif = dev.get_neighbor_local_ipif(session, neighbor_d)
                    neighbor_ip = dev.get_neighbor_ip(session, neighbor_d)
                    if local_if:
                        fabric_device_variables['interfaces'].append({
                            'name': local_if,
                            'ifclass': 'fabric',
                            'ipv4if': local_ipif,
                            'peer_hostname': neighbor_d.hostname,
                            'peer_infra_lo': str(neighbor_d.infra_ip),
                            'peer_ip': str(neighbor_ip),
                            'peer_asn': generate_asn(neighbor_d.infra_ip)
                        })
                        fabric_device_variables['bgp_ipv4_peers'].append({
                            'peer_hostname': neighbor_d.hostname,
                            'peer_infra_lo': str(neighbor_d.infra_ip),
                            'peer_ip': str(neighbor_ip),
                            'peer_asn': generate_asn(neighbor_d.infra_ip)
                        })
            # populate evpn peers data
            for neighbor_d in get_evpn_spines(session, settings):
                if neighbor_d.hostname == dev.hostname:
                    continue
                fabric_device_variables['bgp_evpn_peers'].append({
                    'peer_hostname': neighbor_d.hostname,
                    'peer_infra_lo': str(neighbor_d.infra_ip),
                    'peer_asn': generate_asn(neighbor_d.infra_ip)
                })
            device_variables = {**fabric_device_variables, **device_variables}

    # Add all environment variables starting with TEMPLATE_SECRET_ to
    # the list of configuration variables. The idea is to store secret
    # configuration outside of the templates repository.
    template_secrets = {}
    for env in os.environ:
        if env.startswith('TEMPLATE_SECRET_'):
            template_secrets[env] = os.environ[env]

    # Merge device variables with settings before sending to template rendering
    # Device variables override any names from settings, for example the
    # interfaces list from settings are replaced with an interface list from
    # device variables that contains more information
    template_vars = {**settings, **device_variables, **template_secrets}

    with open('/etc/cnaas-nms/repository.yml', 'r') as db_file:
        repo_config = yaml.safe_load(db_file)
        local_repo_path = repo_config['templates_local']

    mapfile = os.path.join(local_repo_path, platform, 'mapping.yml')
    if not os.path.isfile(mapfile):
        raise RepoStructureException("File {} not found in template repo".format(mapfile))
    with open(mapfile, 'r') as f:
        mapping = yaml.safe_load(f)
        template = mapping[devtype.name]['entrypoint']

    logger.debug("Generate config for host: {}".format(task.host.name))
    r = task.run(task=text.template_file,
                 name="Generate device config",
                 template=template,
                 path=f"{local_repo_path}/{task.host.platform}",
                 **template_vars)

    # TODO: Handle template not found, variables not defined
    # jinja2.exceptions.UndefinedError

    task.host["config"] = r.result
    task.host["template_vars"] = template_vars

    if generate_only:
        task.host["change_score"] = 0
    else:
        logger.debug("Synchronize device config for host: {} ({}:{})".format(
            task.host.name, task.host.hostname, task.host.port))

        task.host.open_connection("napalm", configuration=task.nornir.config)
        task.run(task=networking.napalm_configure,
                 name="Sync device config",
                 replace=True,
                 configuration=task.host["config"],
                 dry_run=dry_run
                 )
        task.host.close_connection("napalm")

        if task.results[1].diff:
            config = task.results[1].host["config"]
            diff = task.results[1].diff
            task.host["change_score"] = calculate_score(config, diff)
        else:
            task.host["change_score"] = 0
    if job_id:
        with redis_session() as db:
            db.lpush('finished_devices_' + str(job_id), task.host.name)


def generate_only(hostname: str) -> (str, dict):
    """
    Generate configuration for a device and return it as a text string.

    Args:
        hostname: Hostname of device generate config for

    Returns:
        (string with config, dict with available template variables)
    """
    logger = get_logger()
    nr = cnaas_init()
    nr_filtered, _, _ = inventory_selector(nr, hostname=hostname)
    template_vars = {}
    if len(nr_filtered.inventory.hosts) != 1:
        raise ValueError("Invalid hostname: {}".format(hostname))
    try:
        nrresult = nr_filtered.run(task=push_sync_device, generate_only=True)
        if nrresult[hostname][0].failed:
            raise Exception("Could not generate config for device {}: {}".format(
                hostname, nrresult[hostname][0].result
            ))
        if "template_vars" in nrresult[hostname][1].host:
            template_vars = nrresult[hostname][1].host["template_vars"]
        if nrresult.failed:
            print_result(nrresult)
            raise Exception("Failed to generate config for {}".format(hostname))

        return nrresult[hostname][1].result, template_vars
    except Exception as e:
        logger.exception("Exception while generating config: {}".format(str(e)))
        if len(nrresult[hostname]) >= 2:
            return nrresult[hostname][1].result, template_vars
        else:
            return str(e), template_vars


def sync_check_hash(task, force=False, job_id=None):
    """
    Start the task which will compare device configuration hashes.

    Args:
        task: Nornir task
        force: Ignore device hash
    """
    set_thread_data(job_id)
    logger = get_logger()
    if force is True:
        return
    with sqla_session() as session:
        stored_hash = Device.get_config_hash(session, task.host.name)
    if stored_hash is None:
        return

    task.host.open_connection("napalm", configuration=task.nornir.config)
    res = task.run(task=napalm_get, getters=["config"])
    task.host.close_connection("napalm")

    running_config = dict(res.result)['config']['running'].encode()
    if running_config is None:
        raise Exception('Failed to get running configuration')
    hash_obj = sha256(running_config)
    running_hash = hash_obj.hexdigest()
    if stored_hash != running_hash:
        raise Exception('Device {} configuration is altered outside of CNaaS!'.format(task.host.name))


def update_config_hash(task):
    logger = get_logger()
    try:
        res = task.run(task=napalm_get, getters=["config"])
        if not isinstance(res, MultiResult) or len(res) != 1 or not isinstance(res[0].result, dict) \
                or 'config' not in res[0].result:
            raise Exception("Unable to get config from device")
        new_config_hash = calc_config_hash(task.host.name, res[0].result['config']['running'])
        if not new_config_hash:
            raise ValueError("Empty config hash")
    except Exception as e:
        logger.exception("Unable to get config hash: {}".format(str(e)))
        raise e
    else:
        with sqla_session() as session:
            Device.set_config_hash(session, task.host.name, new_config_hash)
            logger.debug("Config hash for {} updated to {}".format(task.host.name, new_config_hash))


@job_wrapper
def sync_devices(hostname: Optional[str] = None, device_type: Optional[str] = None,
                 group: Optional[str] = None, dry_run: bool = True, force: bool = False,
                 auto_push: bool = False, job_id: Optional[int] = None,
                 scheduled_by: Optional[str] = None, resync: bool = False) -> NornirJobResult:
    """Synchronize devices to their respective templates. If no arguments
    are specified then synchronize all devices that are currently out
    of sync.

    Args:
        hostname: Specify a single host by hostname to synchronize
        device_type: Specify a device type to synchronize
        group: Specify a group of devices to synchronize
        dry_run: Don't commit generated config to device
        force: Commit config even if changes made outside CNaaS will get
               overwritten
        auto_push: Automatically do live-run after dry-run if change score is low
        job_id: job_id provided by scheduler when adding a new job
        scheduled_by: Username from JWT
        resync: Re-synchronize a device even if it's marked as synced in the
                database, a device selected by hostname is always re-synced

    Returns:
        NornirJobResult
    """
    logger = get_logger()
    nr = cnaas_init()
    dev_count = 0
    skipped_hostnames = []
    if hostname:
        nr_filtered, dev_count, skipped_hostnames = \
            inventory_selector(nr, hostname=hostname)
    else:
        if device_type:
            nr_filtered, dev_count, skipped_hostnames = \
                inventory_selector(nr, resync=resync, device_type=device_type)
        elif group:
            nr_filtered, dev_count, skipped_hostnames = \
                inventory_selector(nr, resync=resync, group=group)
        else:
            # all devices
            nr_filtered, dev_count, skipped_hostnames = \
                inventory_selector(nr, resync=resync)

    if skipped_hostnames:
        logger.info("Device(s) already synchronized, skipping ({}): {}".format(
            len(skipped_hostnames), ", ".join(skipped_hostnames)
        ))

    device_list = list(nr_filtered.inventory.hosts.keys())
    logger.info("Device(s) selected for synchronization ({}): {}".format(
        dev_count, ", ".join(device_list)
    ))

    try:
        nrresult = nr_filtered.run(task=sync_check_hash,
                                   force=force,
                                   job_id=job_id)
    except Exception as e:
        logger.exception("Exception while checking config hash: {}".format(str(e)))
        raise e
    else:
        if nrresult.failed:
            # Mark devices as unsynchronized if config hash check failed
            with sqla_session() as session:
                session.query(Device).filter(Device.hostname.in_(nrresult.failed_hosts.keys())).\
                    update({Device.synchronized: False}, synchronize_session=False)
            raise Exception('Configuration hash check failed for {}'.format(
                ' '.join(nrresult.failed_hosts.keys())))

    if not dry_run:
        with sqla_session() as session:
            logger.info("Trying to acquire lock for devices to run syncto job: {}".format(job_id))
            if not Joblock.acquire_lock(session, name='devices', job_id=job_id):
                raise JoblockError("Unable to acquire lock for configuring devices")

    try:
        nrresult = nr_filtered.run(task=push_sync_device, dry_run=dry_run,
                                   job_id=job_id)
    except Exception as e:
        logger.exception("Exception while synchronizing devices: {}".format(str(e)))
        try:
            if not dry_run:
                with sqla_session() as session:
                    logger.info("Releasing lock for devices from syncto job: {}".format(job_id))
                    Joblock.release_lock(session, job_id=job_id)
        except Exception:
            logger.error("Unable to release devices lock after syncto job")
        return NornirJobResult(nrresult=nrresult)

    failed_hosts = list(nrresult.failed_hosts.keys())
    for hostname in failed_hosts:
        logger.error("Synchronization of device '{}' failed".format(hostname))

    if nrresult.failed:
        logger.error("Not all devices were successfully synchronized")

    total_change_score = 1
    change_scores = []
    changed_hosts = []
    unchanged_hosts = []
    # calculate change impact score
    for host, results in nrresult.items():
        if len(results) != 3:
            logger.debug("Unable to calculate change score for failed device {}".format(host))
        elif results[2].diff:
            changed_hosts.append(host)
            if "change_score" in results[0].host:
                change_scores.append(results[0].host["change_score"])
                logger.debug("Change score for host {}: {:.1f}".format(
                    host, results[0].host["change_score"]))
        else:
            unchanged_hosts.append(host)
            change_scores.append(0)
            logger.debug("Empty diff for host {}, 0 change score".format(
                host))

    if not dry_run:
        def exclude_filter(host, exclude_list=failed_hosts+unchanged_hosts):
            if host.name in exclude_list:
                return False
            else:
                return True

        # set new config hash for devices that was successfully updated
        nr_successful = nr_filtered.filter(filter_func=exclude_filter)
        try:
            nrresult_confighash = nr_successful.run(task=update_config_hash)
        except Exception as e:
            logger.exception("Exception while updating config hashes: {}".format(str(e)))
        else:
            if nrresult_confighash.failed:
                logger.error("Unable to update some config hashes: {}".format(
                    list(nrresult_confighash.failed_hosts.keys())))

    # set devices as synchronized if needed
    with sqla_session() as session:
        for hostname in changed_hosts:
            if dry_run:
                dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
                dev.synchronized = False
            else:
                dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
                dev.synchronized = True
        for hostname in unchanged_hosts:
            dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
            dev.synchronized = True
        if not dry_run:
            logger.info("Releasing lock for devices from syncto job: {}".format(job_id))
            Joblock.release_lock(session, job_id=job_id)

    if len(device_list) == 0:
        total_change_score = 0
    elif not change_scores or total_change_score >= 100 or failed_hosts:
        total_change_score = 100
    else:
        # use individual max as total_change_score, range 1-100
        total_change_score = max(min(int(max(change_scores) + 0.5), 100), 1)
    logger.info(
        "Change impact score: {:.1f} (dry_run: {}, selected devices: {}, changed devices: {})".
            format(total_change_score, dry_run, len(device_list), len(changed_hosts)))

    next_job_id = None
    if auto_push and len(device_list) == 1 and hostname and dry_run:
        if not changed_hosts:
            logger.info("None of the selected host has any changes (diff), skipping auto-push")
        elif total_change_score < AUTOPUSH_MAX_SCORE:
            scheduler = Scheduler()
            next_job_id = scheduler.add_onetime_job(
                'cnaas_nms.confpush.sync_devices:sync_devices',
                when=0,
                scheduled_by=scheduled_by,
                kwargs={'hostname': hostname, 'dry_run': False, 'force': force})
            logger.info(f"Auto-push scheduled live-run of commit as job id {next_job_id}")
        else:
            logger.info(
                f"Auto-push of config to device {hostname} failed because change score of "
                f"{total_change_score} is higher than auto-push limit {AUTOPUSH_MAX_SCORE}"
            )

    return NornirJobResult(nrresult=nrresult, next_job_id=next_job_id, change_score=total_change_score)


def push_static_config(task, config: str, dry_run: bool = True,
                       job_id: Optional[str] = None,
                       scheduled_by: Optional[str] = None):
    """
    Nornir task to push static config to device

    Args:
        task: nornir task, sent by nornir when doing .run()
        config: static config to apply
        dry_run: Don't commit config to device, just do compare/diff
        scheduled_by: username that triggered job

    Returns:
    """
    set_thread_data(job_id)
    logger = get_logger()

    logger.debug("Push static config to device: {}".format(task.host.name))

    task.run(task=networking.napalm_configure,
             name="Push static config",
             replace=True,
             configuration=config,
             dry_run=dry_run
             )


@job_wrapper
def apply_config(hostname: str, config: str, dry_run: bool,
                 job_id: Optional[int] = None,
                 scheduled_by: Optional[str] = None) -> NornirJobResult:
    """Apply a static configuration (from backup etc) to a device.

    Args:
        hostname: Specify a single host by hostname to synchronize
        config: Static configuration to apply
        dry_run: Set to false to actually apply config to device
        job_id: Job ID number
        scheduled_by: Username from JWT

    Returns:
        NornirJobResult
    """
    logger = get_logger()

    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            raise Exception("Device {} not found".format(hostname))
        elif not (dev.state == DeviceState.MANAGED or dev.state == DeviceState.UNMANAGED):
            raise Exception("Device {} is in invalid state: {}".format(hostname, dev.state))
        if not dry_run:
            dev.state = DeviceState.UNMANAGED
            dev.synchronized = False

    nr = cnaas_init()
    nr_filtered, _, _ = inventory_selector(nr, hostname=hostname)

    try:
        nrresult = nr_filtered.run(task=push_static_config,
                                   config=config,
                                   dry_run=dry_run,
                                   job_id=job_id)
    except Exception as e:
        logger.exception("Exception in apply_config: {}".format(e))

    return NornirJobResult(nrresult=nrresult)

