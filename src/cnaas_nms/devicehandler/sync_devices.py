import datetime
import os
import time
from hashlib import sha256
from ipaddress import IPv4Address, IPv4Interface, ip_interface
from typing import List, Optional, Tuple

import yaml
from napalm.eos import EOSDriver as NapalmEOSDriver
from napalm.junos import JunOSDriver as NapalmJunOSDriver
from nornir.core import Nornir
from nornir.core.task import MultiResult, Result
from nornir_jinja2.plugins.tasks import template_file
from nornir_napalm.plugins.tasks import napalm_configure, napalm_get
from nornir_utils.plugins.functions import print_result

import cnaas_nms.db.helper
from cnaas_nms.app_settings import api_settings, app_settings
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.device_vars import expand_interface_settings
from cnaas_nms.db.git import RepoStructureException
from cnaas_nms.db.interface import Interface
from cnaas_nms.db.joblock import Joblock, JoblockError
from cnaas_nms.db.session import redis_session, sqla_session
from cnaas_nms.db.settings import get_settings
from cnaas_nms.devicehandler.changescore import calculate_score
from cnaas_nms.devicehandler.get import calc_config_hash
from cnaas_nms.devicehandler.nornir_helper import NornirJobResult, cnaas_init, get_jinja_env, inventory_selector
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.scheduler.thread_data import set_thread_data
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.tools.jinja_helpers import get_environment_secrets
from cnaas_nms.tools.log import get_logger

AUTOPUSH_MAX_SCORE = 10
PRIVATE_ASN_START = 4200000000


def generate_asn(ipv4_address: IPv4Address) -> Optional[int]:
    """Generate a unique private 4 byte AS number based on last two octets of
    an IPv4 address (infra_lo)"""
    return PRIVATE_ASN_START + (ipv4_address.packed[2] * 256 + ipv4_address.packed[3])


def get_evpn_peers(session, settings: dict):
    logger = get_logger()
    device_hostnames = []
    for entry in settings["evpn_peers"]:
        if "hostname" in entry and Device.valid_hostname(entry["hostname"]):
            device_hostnames.append(entry["hostname"])
        else:
            logger.error("Invalid entry specified in settings->evpn_peers, ignoring: {}".format(entry))
    ret = []
    for hostname in device_hostnames:
        dev = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if dev:
            ret.append(dev)
    # If no evpn_peers were specified return a list of all CORE devices instead
    if not ret:
        core_devs = session.query(Device).filter(Device.device_type == DeviceType.CORE).all()
        for dev in core_devs:
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
            if vxlan_data["vlan_name"] == vlan_name:
                return int(vxlan_data["vlan_id"])
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
    ret = {"mlag_peer": False, "mlag_peer_hostname": None, "mlag_peer_low": None}
    mlag_peer: Device = dev.get_mlag_peer(session)
    if not mlag_peer:
        return ret
    ret["mlag_peer"] = True
    ret["mlag_peer_hostname"] = mlag_peer.hostname
    if dev.id < mlag_peer.id:
        ret["mlag_peer_low"] = True
    else:
        ret["mlag_peer_low"] = False
    return ret


def populate_device_vars(
    session, dev: Device, ztp_hostname: Optional[str] = None, ztp_devtype: Optional[DeviceType] = None
):
    logger = get_logger()
    device_variables = {
        "device_model": dev.model,
        "device_os_version": dev.os_version,
        "device_id": dev.id,
        "hostname": dev.hostname,
        "stack_members": []
        # 'host' variable is also implicitly added by nornir-jinja2
    }

    if len(dev.stack_members) > 0:
        device_variables["stack_members"] = [
            {"priority": member.priority, "hardware_id": member.hardware_id, "member_no": member.member_no}
            for member in dev.stack_members
        ]

    if ztp_hostname:
        hostname: str = ztp_hostname
    else:
        hostname: str = dev.hostname

    if ztp_devtype:
        devtype: DeviceType = ztp_devtype
    elif dev.device_type != DeviceType.UNKNOWN:
        devtype: DeviceType = dev.device_type
    else:
        raise Exception("Can't populate device vars for device type UNKNOWN")

    mgmt_ip = dev.management_ip
    if not ztp_hostname:
        if not mgmt_ip:
            raise Exception("Could not find management IP for device {}".format(hostname))
        else:
            device_variables["mgmt_ip"] = str(mgmt_ip)

    if not isinstance(dev.platform, str):
        raise ValueError("Unknown platform: {}".format(dev.platform))

    settings, settings_origin = get_settings(hostname, devtype, dev.model)

    if devtype == DeviceType.ACCESS:
        if ztp_hostname:
            access_device_variables = {"interfaces": []}
        else:
            mgmtdomain = cnaas_nms.db.helper.find_mgmtdomain_by_ip(session, dev.management_ip)
            if not mgmtdomain:
                raise Exception(
                    "Could not find appropriate management domain for management_ip: {}".format(dev.management_ip)
                )

            mgmt_gw_ipif = ip_interface(mgmtdomain.primary_gw)
            access_device_variables = {
                "mgmt_vlan_id": mgmtdomain.vlan,
                "mgmt_gw": str(mgmt_gw_ipif.ip),
                "mgmt_ipif": str(ip_interface("{}/{}".format(mgmt_ip, mgmt_gw_ipif.network.prefixlen))),
                "mgmt_ip": str(mgmt_ip),
                "mgmt_prefixlen": int(mgmt_gw_ipif.network.prefixlen),
                "interfaces": [],
            }
            if dev.secondary_management_ip:
                secondary_mgmt_gw_ipif = ip_interface(mgmtdomain.secondary_gw)
                access_device_variables.update(
                    {
                        "secondary_mgmt_ipif": str(
                            ip_interface(
                                "{}/{}".format(dev.secondary_management_ip, secondary_mgmt_gw_ipif.network.prefixlen)
                            )
                        ),
                        "secondary_mgmt_ip": dev.secondary_management_ip,
                        "secondary_mgmt_prefixlen": int(secondary_mgmt_gw_ipif.network.prefixlen),
                        "secondary_mgmt_gw": secondary_mgmt_gw_ipif.ip,
                    }
                )

        # Check peer names for populating description on ACCESS_DOWNLINK ports
        ifname_peer_map = dev.get_linknet_localif_mapping(session)

        intfs = session.query(Interface).filter(Interface.device == dev).all()
        intf: Interface
        for intf in intfs:
            untagged_vlan: Optional[int] = None
            tagged_vlan_list: List = []
            intfdata: Optional[dict] = None
            try:
                ifindexnum: int = Interface.interface_index_num(intf.name)
            except ValueError:
                ifindexnum: int = 0
            if intf.data:
                if "untagged_vlan" in intf.data:
                    untagged_vlan = resolve_vlanid(intf.data["untagged_vlan"], settings["vxlans"])
                if "tagged_vlan_list" in intf.data:
                    tagged_vlan_list = resolve_vlanid_list(intf.data["tagged_vlan_list"], settings["vxlans"])
                intfdata = dict(intf.data)
            if intf.name in ifname_peer_map:
                if isinstance(intfdata, dict):
                    intfdata["description"] = ifname_peer_map[intf.name]
                else:
                    intfdata = {"description": ifname_peer_map[intf.name]}

            access_device_variables["interfaces"].append(
                {
                    "name": intf.name,
                    "ifclass": intf.configtype.name,
                    "untagged_vlan": untagged_vlan,
                    "tagged_vlan_list": tagged_vlan_list,
                    "data": intfdata,
                    "indexnum": ifindexnum,
                }
            )
        mlag_vars = get_mlag_vars(session, dev)
        device_variables = {**device_variables, **access_device_variables, **mlag_vars}
    elif devtype == DeviceType.DIST or devtype == DeviceType.CORE:
        infra_ip = dev.infra_ip
        asn = generate_asn(infra_ip)
        fabric_device_variables = {
            "interfaces": [],
            "bgp_ipv4_peers": [],
            "bgp_evpn_peers": [],
            "mgmtdomains": [],
            "asn": asn,
        }
        if mgmt_ip and infra_ip:
            mgmt_device_variables = {
                "mgmt_ipif": str(IPv4Interface("{}/32".format(mgmt_ip))),
                "mgmt_prefixlen": 32,
                "infra_ipif": str(IPv4Interface("{}/32".format(infra_ip))),
                "infra_ip": str(infra_ip),
            }
            fabric_device_variables = {**fabric_device_variables, **mgmt_device_variables}
        # find fabric neighbors
        fabric_interfaces = {}
        for neighbor_d in dev.get_neighbors(session):
            if neighbor_d.device_type == DeviceType.DIST or neighbor_d.device_type == DeviceType.CORE:
                for linknet in dev.get_links_to(session, neighbor_d):
                    local_if = linknet.get_port(dev.id)
                    local_ipif = linknet.get_ipif(dev.id)
                    neighbor_ip = linknet.get_ip(neighbor_d.id)
                    if local_if:
                        fabric_interfaces[local_if] = {
                            "name": local_if,
                            "ifclass": "fabric",
                            "ipv4if": local_ipif,
                            "peer_hostname": neighbor_d.hostname,
                            "peer_infra_lo": str(neighbor_d.infra_ip),
                            "peer_ip": str(neighbor_ip),
                            "peer_asn": generate_asn(neighbor_d.infra_ip),
                        }
                        fabric_device_variables["bgp_ipv4_peers"].append(
                            {
                                "peer_hostname": neighbor_d.hostname,
                                "peer_infra_lo": str(neighbor_d.infra_ip),
                                "peer_ip": str(neighbor_ip),
                                "peer_asn": generate_asn(neighbor_d.infra_ip),
                            }
                        )
        ifname_peer_map = dev.get_linknet_localif_mapping(session)
        if "interfaces" in settings and settings["interfaces"]:
            for intf in expand_interface_settings(settings["interfaces"]):
                try:
                    ifindexnum: int = Interface.interface_index_num(intf["name"])
                except ValueError:
                    ifindexnum: int = 0
                if "ifclass" not in intf:
                    continue
                if intf["ifclass"] == "downlink":
                    data = {}
                    if intf["name"] in ifname_peer_map:
                        data["description"] = ifname_peer_map[intf["name"]]
                    fabric_device_variables["interfaces"].append(
                        {
                            "name": intf["name"],
                            "ifclass": intf["ifclass"],
                            "redundant_link": intf["redundant_link"],
                            "indexnum": ifindexnum,
                            "data": data,
                        }
                    )
                elif intf["ifclass"] == "custom":
                    fabric_device_variables["interfaces"].append(
                        {
                            "name": intf["name"],
                            "ifclass": intf["ifclass"],
                            "config": intf["config"],
                            "indexnum": ifindexnum,
                        }
                    )
                elif intf["ifclass"] == "fabric":
                    if intf["name"] in fabric_interfaces:
                        fabric_device_variables["interfaces"].append(
                            {**fabric_interfaces[intf["name"]], **{"indexnum": ifindexnum}}
                        )
                        del fabric_interfaces[intf["name"]]
                    else:
                        fabric_device_variables["interfaces"].append(
                            {
                                "name": intf["name"],
                                "ifclass": intf["ifclass"],
                                "indexnum": ifindexnum,
                                "ipv4if": None,
                                "peer_hostname": "ztp",
                                "peer_infra_lo": None,
                                "peer_ip": None,
                                "peer_asn": None,
                            }
                        )
                else:
                    if_dict = {"indexnum": ifindexnum}
                    for key, value in intf.items():
                        if_dict[key] = value
                    fabric_device_variables["interfaces"].append(if_dict)

        for local_if, data in fabric_interfaces.items():
            logger.warn(
                f"Interface {local_if} on device {hostname} not " "configured as linknet because of wrong ifclass"
            )

        if not ztp_hostname:
            for mgmtdom in cnaas_nms.db.helper.get_all_mgmtdomains(session, hostname):
                fabric_device_variables["mgmtdomains"].append(
                    {
                        "id": mgmtdom.id,
                        "ipv4_gw": mgmtdom.ipv4_gw,
                        "vlan": mgmtdom.vlan,
                        "description": mgmtdom.description,
                        "esi_mac": mgmtdom.esi_mac,
                        "ipv4_ip": str(mgmtdom.device_a_ip)
                        if hostname == mgmtdom.device_a.hostname
                        else str(mgmtdom.device_b_ip),
                    }
                )
        # populate evpn peers data
        for neighbor_d in get_evpn_peers(session, settings):
            if neighbor_d.hostname == dev.hostname:
                continue
            fabric_device_variables["bgp_evpn_peers"].append(
                {
                    "peer_hostname": neighbor_d.hostname,
                    "peer_infra_lo": str(neighbor_d.infra_ip),
                    "peer_asn": generate_asn(neighbor_d.infra_ip),
                }
            )
        device_variables = {**device_variables, **fabric_device_variables}

    # Add all environment variables starting with TEMPLATE_SECRET_ to
    # the list of configuration variables. The idea is to store secret
    # configuration outside of the templates repository.
    template_secrets = get_environment_secrets()
    # For testing purposes allow overriding of settings instead of requiring git updates
    override_dict = {}
    if api_settings.SETTINGS_OVERRIDE and isinstance(api_settings.SETTINGS_OVERRIDE, dict):
        override_dict = api_settings.SETTINGS_OVERRIDE
    # Merge all dicts with variables into one, later row overrides
    # Device variables override any names from settings, for example the
    # interfaces list from settings are replaced with an interface list from
    # device variables that contains more information
    device_variables = {**settings, **device_variables, **template_secrets, **override_dict}
    return device_variables


def get_confirm_mode(confirm_mode_override: Optional[int] = None) -> int:
    valid_modes = [0, 1, 2]
    if confirm_mode_override and confirm_mode_override in valid_modes:
        return confirm_mode_override
    elif api_settings.COMMIT_CONFIRMED_MODE and api_settings.COMMIT_CONFIRMED_MODE in valid_modes:
        return api_settings.COMMIT_CONFIRMED_MODE
    else:
        return 1


def post_sync_update_cofighash(
    dry_run: bool, force: bool, nr_filtered: Nornir, unchanged_hosts: List, failed_hosts: List
):
    """Update configuration hashes for device that were configured after sync has completed.
    Args:
        dry_run: bool
        force: bool
        nr_filtered: Nornir inventory of hosts to run on
        unchanged_hosts: List of hosts that has not been changed, don't update confhosh
        failed_hosts: List of hosts that failed with change, don't update confhash
    """
    logger = get_logger()
    nr_confighash = None
    if dry_run and force:
        # update config hash for devices that had an empty diff because local
        # changes on a device can cause reordering of CLI commands that results
        # in config hash mismatch even if the calculated diff was empty
        def include_filter(host, include_list=unchanged_hosts):
            if host.name in include_list:
                return True
            else:
                return False

        nr_confighash = nr_filtered.filter(filter_func=include_filter)
    elif not dry_run:
        # set new config hash for devices that was successfully updated
        def exclude_filter(host, exclude_list=failed_hosts + unchanged_hosts):
            if host.name in exclude_list:
                return False
            else:
                return True

        nr_confighash = nr_filtered.filter(filter_func=exclude_filter)

    if nr_confighash:
        try:
            nrresult_confighash = nr_confighash.run(task=update_config_hash)
        except Exception as e:
            logger.exception("Exception while updating config hashes: {}".format(str(e)))
        else:
            if nrresult_confighash.failed:
                logger.error(
                    "Unable to update some config hashes: {}".format(list(nrresult_confighash.failed_hosts.keys()))
                )


def napalm_configure_confirmed(
    task,
    dry_run=None,
    configuration=None,
    replace=None,
    commit_message: str = "",
    job_id: int = 0,
    confirm_mode_override: Optional[int] = None,
):
    """Configure device and set configure confirmed timeout to revert changes unless a confirm is received"""
    logger = get_logger()
    n_device = task.host.get_connection("napalm", task.nornir.config)
    if isinstance(n_device, NapalmEOSDriver):
        n_device.config_session = "job{}".format(job_id)
    n_device.load_replace_candidate(config=configuration)
    diff = n_device.compare_config()
    if diff:
        n_device.commit_config(revert_in=api_settings.COMMIT_CONFIRMED_TIMEOUT)
        mode_2_supported = False
        if get_confirm_mode(confirm_mode_override) == 2:
            if isinstance(n_device, (NapalmEOSDriver, NapalmJunOSDriver)):
                mode_2_supported = True
            else:
                logger.warn(
                    f"commit_confirmed_mode is set to 2, but it's unsupported for device OS '{task.host.platform}'. "
                    f"Falling back to mode 1 for device: {task.host.name}."
                )

        if get_confirm_mode(confirm_mode_override) == 1 or not mode_2_supported:
            if n_device.has_pending_commit():
                n_device.confirm_commit()
            else:
                n_device.discard_config()
    else:
        n_device.discard_config()
    return Result(host=task.host, diff=diff, changed=len(diff) > 0)


def napalm_confirm_commit(task, job_id: int, prev_job_id: int):
    """Confirm a previous pending configure session"""
    set_thread_data(job_id)
    logger = get_logger()
    n_device = task.host.get_connection("napalm", task.nornir.config)
    if isinstance(n_device, NapalmEOSDriver):
        n_device.config_session = "job{}".format(prev_job_id)
        n_device.confirm_commit()
    elif isinstance(n_device, NapalmJunOSDriver):
        n_device.confirm_commit()
    logger.debug("Commit for job {} confirmed on device {}".format(prev_job_id, task.host.name))
    if job_id:
        with redis_session() as db:
            db.lpush("finished_devices_" + str(job_id), task.host.name)


def push_sync_device(
    task,
    dry_run: bool = True,
    generate_only: bool = False,
    job_id: Optional[str] = None,
    scheduled_by: Optional[str] = None,
    confirm_mode_override: Optional[int] = None,
):
    """
    Nornir task to generate config and push to device

    Args:
        task: nornir task, sent by nornir when doing .run()
        dry_run: Don't commit config to device, just do compare/diff
        generate_only: Only generate text config, don't try to commit or
                       even do dry_run compare to running config
        job_id: Job ID integer
        scheduled_by: username of users that scheduled job
        confirm_mode_override: integer to specify commit confirm mode
    Returns:

    """
    set_thread_data(job_id)
    logger = get_logger()
    hostname = task.host.name
    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
        template_vars = populate_device_vars(session, dev)
        platform = dev.platform
        devtype = dev.device_type

    local_repo_path = app_settings.TEMPLATES_LOCAL

    mapfile = os.path.join(local_repo_path, platform, "mapping.yml")
    if not os.path.isfile(mapfile):
        raise RepoStructureException("File {} not found in template repo".format(mapfile))
    with open(mapfile, "r") as f:
        mapping = yaml.safe_load(f)
        template = mapping[devtype.name]["entrypoint"]

    logger.debug("Generate config for host: {}".format(task.host.name))
    r = task.run(
        task=template_file,
        name="Generate device config",
        template=template,
        jinja_env=get_jinja_env(f"{local_repo_path}/{task.host.platform}"),
        path=f"{local_repo_path}/{task.host.platform}",
        **template_vars,
    )

    # TODO: Handle template not found, variables not defined
    # jinja2.exceptions.UndefinedError

    task.host["config"] = r.result
    task.host["template_vars"] = template_vars

    if generate_only:
        task.host["change_score"] = 0
    else:
        logger.debug(
            "Synchronize device config for host: {} ({}:{})".format(task.host.name, task.host.hostname, task.host.port)
        )

        if api_settings.COMMIT_CONFIRMED_MODE != 2:
            task.host.open_connection("napalm", configuration=task.nornir.config)
        task_args = {
            "name": "Sync device config",
            "replace": True,
            "configuration": task.host["config"],
            "dry_run": dry_run,
            "commit_message": "Job id {}".format(job_id),
        }
        if dry_run:
            task_args["task"] = napalm_configure
        elif api_settings.COMMIT_CONFIRMED_MODE == 0:
            task_args["task"] = napalm_configure
        else:
            task_args["task"] = napalm_configure_confirmed
            task_args["job_id"] = job_id
            task_args["confirm_mode_override"] = confirm_mode_override
        logger.debug(
            "Commit confirm mode for host {}: {} (dry_run: {})".format(
                task.host.name, api_settings.COMMIT_CONFIRMED_MODE, dry_run
            )
        )
        task.run(**task_args)
        if api_settings.COMMIT_CONFIRMED_MODE != 2:
            task.host.close_connection("napalm")

        if task.results[1].diff:
            config = task.results[1].host["config"]
            diff = task.results[1].diff
            task.host["change_score"] = calculate_score(config, diff)
        else:
            task.host["change_score"] = 0
    if job_id:
        with redis_session() as db:
            db.lpush("finished_devices_" + str(job_id), task.host.name)


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
            raise Exception(
                "Could not generate config for device {}: {}".format(hostname, nrresult[hostname][0].result)
            )
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
    if force is True:
        return
    with sqla_session() as session:
        stored_hash = Device.get_config_hash(session, task.host.name)
    if stored_hash is None:
        return

    task.host.open_connection("napalm", configuration=task.nornir.config)
    res = task.run(task=napalm_get, getters=["config"])
    task.host.close_connection("napalm")

    running_config = dict(res.result)["config"]["running"].encode()
    if running_config is None:
        raise Exception("Failed to get running configuration")
    hash_obj = sha256(running_config)
    running_hash = hash_obj.hexdigest()
    if stored_hash != running_hash:
        raise Exception("Device {} configuration is altered outside of CNaaS!".format(task.host.name))


def update_config_hash(task):
    logger = get_logger()
    try:
        res = task.run(task=napalm_get, getters=["config"])
        if (
            not isinstance(res, MultiResult)
            or len(res) != 1
            or not isinstance(res[0].result, dict)
            or "config" not in res[0].result
        ):
            raise Exception("Unable to get config from device")
        new_config_hash = calc_config_hash(task.host.name, res[0].result["config"]["running"])
        if not new_config_hash:
            raise ValueError("Empty config hash")
    except Exception as e:
        logger.exception("Unable to get config hash: {}".format(str(e)))
        raise e
    else:
        with sqla_session() as session:
            Device.set_config_hash(session, task.host.name, new_config_hash)
            logger.debug("Config hash for {} updated to {}".format(task.host.name, new_config_hash))


def confcheck_devices(session, hostnames: List[str], job_id=None):
    nr = cnaas_init()
    nr_filtered, dev_count, skipped_hostnames = inventory_selector(nr, hostname=hostnames)

    try:
        nrresult = nr_filtered.run(task=sync_check_hash, job_id=job_id)
    except Exception as e:
        raise e
    else:
        if nrresult.failed:
            for hostname in nrresult.failed_hosts.keys():
                dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
                dev.synchronized = False
            raise Exception("Configuration hash check failed for {}".format(" ".join(nrresult.failed_hosts.keys())))


def select_devices(
    nr: Nornir,
    hostnames: Optional[List[str]] = None,
    device_type: Optional[str] = None,
    group: Optional[str] = None,
    resync: bool = False,
    **kwargs,
) -> Tuple[Nornir, int, List[str]]:
    """Get device selection for devices to synchronize.

    Returns:
        Nornir: A filtered Nornir object based on the input arg nr
        int: A count of number of devices selected
        List[str]: A list of hostnames that will be skipped from the initial nr object
    """
    logger = get_logger()
    if hostnames:
        nr_filtered, dev_count, skipped_hostnames = inventory_selector(nr, hostname=hostnames)
    else:
        if device_type:
            nr_filtered, dev_count, skipped_hostnames = inventory_selector(nr, resync=resync, device_type=device_type)
        elif group:
            nr_filtered, dev_count, skipped_hostnames = inventory_selector(nr, resync=resync, group=group)
        else:
            # all devices
            nr_filtered, dev_count, skipped_hostnames = inventory_selector(nr, resync=resync)

    if skipped_hostnames:
        logger.info(
            "Device(s) already synchronized, skipping ({}): {}".format(
                len(skipped_hostnames), ", ".join(skipped_hostnames)
            )
        )

    if dev_count > 50 and api_settings.COMMIT_CONFIRMED_MODE == 2:
        logger.warning("commit_confirmed_mode 2 might not be reliable for syncs of more than 50 devices")

    return nr_filtered, dev_count, skipped_hostnames


@job_wrapper
def confirm_devices(
    prev_job_id: int,
    hostnames: List[str],
    job_id: Optional[int] = None,
    scheduled_by: Optional[str] = None,
    resync: bool = False,
) -> NornirJobResult:
    logger = get_logger()
    nr = cnaas_init()

    nr_filtered, dev_count, skipped_hostnames = select_devices(nr, hostnames, resync)

    device_list = list(nr_filtered.inventory.hosts.keys())
    logger.info("Device(s) selected for commit-confirm ({}): {}".format(dev_count, ", ".join(device_list)))

    try:
        nrresult = nr_filtered.run(task=napalm_confirm_commit, job_id=job_id, prev_job_id=prev_job_id)
    except Exception as e:
        logger.exception("Exception while confirm-commit devices: {}".format(str(e)))
        try:
            with sqla_session() as session:
                logger.info(
                    "Releasing lock for devices from syncto job: {} (in commit-job {})".format(prev_job_id, job_id)
                )
                Joblock.release_lock(session, job_id=prev_job_id)
        except Exception:
            logger.error("Unable to release devices lock after syncto job")
        return NornirJobResult(nrresult=nrresult)

    failed_hosts = list(nrresult.failed_hosts.keys())
    for hostname in failed_hosts:
        logger.error("Commit-confirm failed for device '{}'".format(hostname))

    # mark synced, remove mark sync and release job from sync_devices. break into functions?
    if nrresult.failed:
        logger.error("Not all devices were successfully commit-confirmed")

    post_sync_update_cofighash(
        dry_run=False, force=False, nr_filtered=nr_filtered, unchanged_hosts=[], failed_hosts=failed_hosts
    )

    with sqla_session() as session:
        for host, results in nrresult.items():
            if host in failed_hosts or len(results) != 1:
                logger.debug("Setting device as unsync for failed commit-confirm on device {}".format(host))
                dev: Device = session.query(Device).filter(Device.hostname == host).one()
                dev.synchronized = False
                dev.confhash = None
            else:
                dev: Device = session.query(Device).filter(Device.hostname == host).one()
                dev.synchronized = True
                dev.last_seen = datetime.datetime.utcnow()

        logger.info("Releasing lock for devices from syncto job: {} (in commit-job {})".format(prev_job_id, job_id))
        Joblock.release_lock(session, job_id=prev_job_id)

    return NornirJobResult(nrresult=nrresult)


@job_wrapper
def sync_devices(
    hostnames: Optional[List[str]] = None,
    device_type: Optional[str] = None,
    group: Optional[str] = None,
    dry_run: bool = True,
    force: bool = False,
    auto_push: bool = False,
    job_id: Optional[int] = None,
    scheduled_by: Optional[str] = None,
    resync: bool = False,
    confirm_mode_override: Optional[int] = None,
) -> NornirJobResult:
    """Synchronize devices to their respective templates. If no arguments
    are specified then synchronize all devices that are currently out
    of sync.

    Args:
        hostnames: Specify a single host by hostname to synchronize
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
        confirm_mode_override: Override settings commit confirm mode, optional int
                               with value 0, 1 or 2

    Returns:
        NornirJobResult
    """
    logger = get_logger()
    nr = cnaas_init()
    nr_filtered, dev_count, skipped_hostnames = select_devices(nr, hostnames, device_type, group, resync)

    device_list = list(nr_filtered.inventory.hosts.keys())
    logger.info("Device(s) selected for synchronization ({}): {}".format(dev_count, ", ".join(device_list)))

    try:
        nrresult = nr_filtered.run(task=sync_check_hash, force=force, job_id=job_id)
    except Exception as e:
        logger.exception("Exception while checking config hash: {}".format(str(e)))
        raise e
    else:
        if nrresult.failed:
            # Mark devices as unsynchronized if config hash check failed
            with sqla_session() as session:
                session.query(Device).filter(Device.hostname.in_(nrresult.failed_hosts.keys())).update(
                    {Device.synchronized: False}, synchronize_session=False
                )
            raise Exception("Configuration hash check failed for {}".format(" ".join(nrresult.failed_hosts.keys())))

    if not dry_run:
        with sqla_session() as session:
            logger.info("Trying to acquire lock for devices to run syncto job: {}".format(job_id))
            max_attempts = 5
            lock_ok: bool = False
            for i in range(max_attempts):
                lock_ok = Joblock.acquire_lock(session, name="devices", job_id=job_id)
                if lock_ok:
                    break
                else:
                    time.sleep(2)
            if not lock_ok:
                raise JoblockError("Unable to acquire lock for configuring devices")

    try:
        nrresult = nr_filtered.run(
            task=push_sync_device,
            dry_run=dry_run,
            job_id=job_id,
            confirm_mode_override=get_confirm_mode(confirm_mode_override),
        )
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
        if host in failed_hosts or len(results) != 3:
            logger.debug("Unable to calculate change score for failed device {}".format(host))
        elif results[2].diff:
            changed_hosts.append(host)
            if "change_score" in results[0].host:
                change_scores.append(results[0].host["change_score"])
                logger.debug("Change score for host {}: {:.1f}".format(host, results[0].host["change_score"]))
        else:
            unchanged_hosts.append(host)
            change_scores.append(0)
            logger.debug("Empty diff for host {}, 0 change score".format(host))

    if get_confirm_mode(confirm_mode_override) != 2:
        post_sync_update_cofighash(
            dry_run=dry_run,
            force=force,
            nr_filtered=nr_filtered,
            unchanged_hosts=unchanged_hosts,
            failed_hosts=failed_hosts,
        )

    # set devices as synchronized if needed
    with sqla_session() as session:
        for hostname in changed_hosts:
            if dry_run:
                dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
                dev.synchronized = False
                dev.last_seen = datetime.datetime.utcnow()
            # if next job will commit, that job will mark synchronized on success
            elif get_confirm_mode(confirm_mode_override) != 2:
                dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
                dev.synchronized = True
                dev.last_seen = datetime.datetime.utcnow()
        for hostname in unchanged_hosts:
            dev: Device = session.query(Device).filter(Device.hostname == hostname).one()
            dev.synchronized = True
            dev.last_seen = datetime.datetime.utcnow()
        if not dry_run and get_confirm_mode(confirm_mode_override) != 2:
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
        "Change impact score: {:.1f} (dry_run: {}, selected devices: {}, changed devices: {})".format(
            total_change_score, dry_run, len(device_list), len(changed_hosts)
        )
    )

    next_job_id = None
    if auto_push and len(device_list) == 1 and hostnames and dry_run:
        if not changed_hosts:
            logger.info("None of the selected host has any changes (diff), skipping auto-push")
        elif total_change_score < AUTOPUSH_MAX_SCORE:
            scheduler = Scheduler()
            next_job_id = scheduler.add_onetime_job(
                "cnaas_nms.devicehandler.sync_devices:sync_devices",
                when=0,
                scheduled_by=scheduled_by,
                kwargs={"hostnames": hostnames, "dry_run": False, "force": force},
            )
            logger.info(f"Auto-push scheduled live-run of commit as job id {next_job_id}")
        else:
            logger.info(
                f"Auto-push of config to device {hostnames} failed because change score of "
                f"{total_change_score} is higher than auto-push limit {AUTOPUSH_MAX_SCORE}"
            )
    elif get_confirm_mode(confirm_mode_override) == 2 and not dry_run:
        if not changed_hosts:
            logger.info("None of the selected host has any changes (diff), skipping commit-confirm")
            logger.info("Releasing lock for devices from syncto job: {}".format(job_id))
            Joblock.release_lock(session, job_id=job_id)
        elif len(failed_hosts) > 0:
            logger.error(
                "No confirm job scheduled since one or more devices failed in commitmode 2"
                ", all devices will rollback in {}s".format(api_settings.COMMIT_CONFIRMED_TIMEOUT)
            )
            time.sleep(api_settings.COMMIT_CONFIRMED_TIMEOUT)
            logger.info("Releasing lock for devices from syncto job: {}".format(job_id))
            Joblock.release_lock(session, job_id=job_id)
        else:
            scheduler = Scheduler()
            next_job_id = scheduler.add_onetime_job(
                "cnaas_nms.devicehandler.sync_devices:confirm_devices",
                when=0,
                scheduled_by=scheduled_by,
                kwargs={"prev_job_id": job_id, "hostnames": changed_hosts},
            )
            logger.info(f"Commit-confirm for job id {job_id} scheduled as job id {next_job_id}")

    return NornirJobResult(nrresult=nrresult, next_job_id=next_job_id, change_score=total_change_score)


def push_static_config(
    task, config: str, dry_run: bool = True, job_id: Optional[str] = None, scheduled_by: Optional[str] = None
):
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

    task.run(task=napalm_configure, name="Push static config", replace=True, configuration=config, dry_run=dry_run)


@job_wrapper
def apply_config(
    hostname: str, config: str, dry_run: bool, job_id: Optional[int] = None, scheduled_by: Optional[str] = None
) -> NornirJobResult:
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

    nr = cnaas_init()
    nr_filtered, _, _ = inventory_selector(nr, hostname=hostname)

    try:
        nrresult = nr_filtered.run(task=push_static_config, config=config, dry_run=dry_run, job_id=job_id)
    except Exception as e:
        logger.exception("Exception in apply_config: {}".format(e))
    else:
        if not dry_run:
            with sqla_session() as session:
                dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
                dev.state = DeviceState.UNMANAGED
                dev.synchronized = False

    return NornirJobResult(nrresult=nrresult)
