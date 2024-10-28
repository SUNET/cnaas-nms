import importlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import pkg_resources
import yaml
from pydantic import ValidationError
from redis import StrictRedis
from redis_lru import RedisLRU

from cnaas_nms.app_settings import api_settings, app_settings
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.git_worktrees import refresh_templates_worktree
from cnaas_nms.db.mgmtdomain import Mgmtdomain
from cnaas_nms.db.session import redis_session, sqla_session
from cnaas_nms.db.settings_fields import f_groups
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.mergedict import merge_dict_origin


def get_settings_root():
    logger = get_logger()
    try:
        settings_fields_path = os.getenv("PLUGIN_SETTINGS_FIELDS_MODULE", "cnaas_nms.plugins.settings_fields")
        settings_fields = importlib.import_module(settings_fields_path)
        f_root_ret = settings_fields.f_root
        logger.debug("Loaded settings_fields module from plugin: {}".format(settings_fields_path))
    except ModuleNotFoundError:
        f_root_ret = importlib.import_module("cnaas_nms.db.settings_fields").f_root
        logger.debug("Loaded settings_fields module from bundled cnaas-nms")
    except Exception as e:
        logger.error("Unable to load plugin module for settings_fields: {}".format(e))
        f_root_ret = importlib.import_module("cnaas_nms.db.settings_fields").f_root
    return f_root_ret


f_root = get_settings_root()

redis_client = StrictRedis(
    host=app_settings.REDIS_HOSTNAME, port=app_settings.REDIS_PORT, retry_on_timeout=True, socket_keepalive=True
)
redis_lru_cache = RedisLRU(redis_client, default_ttl=24 * 3600)


class VerifyPathException(Exception):
    pass


class SettingsSyntaxError(Exception):
    pass


class VlanConflictError(Exception):
    pass


DIR_STRUCTURE_HOST = {"base_system.yml": "file", "interfaces.yml": "file", "routing.yml": "file"}

DIR_STRUCTURE = {
    "global": {"base_system.yml": "file", "groups.yml": "file", "routing.yml": "file", "vxlans.yml": "file"},
    "fabric": {"base_system.yml": "file"},
    "core": {"base_system.yml": "file"},
    "dist": {"base_system.yml": "file"},
    "access": {"base_system.yml": "file"},
    "devices": {Device: DIR_STRUCTURE_HOST},
    "groups": {"group": DIR_STRUCTURE_HOST},
}

MODEL_IF_REGEX = re.compile(r"^interfaces_(.*)\.yml$")


def get_model_specific_configfiles(only_modelname: bool = False) -> dict:
    """Return all model specific configuration file names.

    only_modelname: only show the model name part of the filename

    Returns:
        dict: dictionary with devtype as key and list of filenames as values

        {
            'CORE': [],
            'DIST': ['interfaces_veos.yml']
        }
    """
    ret = {"CORE": [], "DIST": []}
    local_repo_path = app_settings.SETTINGS_LOCAL

    for devtype in ["CORE", "DIST"]:
        for filename in os.listdir(os.path.join(local_repo_path, devtype.lower())):
            m = re.match(MODEL_IF_REGEX, filename)
            if m:
                if only_modelname:
                    ret[devtype].append(m.groups()[0])
                else:
                    ret[devtype].append(filename)
    return ret


def model_name_sanitize(model_name: str):
    """Return the model name sanitized for filename purposes,
    strip whitespace, convert to lowercase etc."""
    ret_name = model_name.strip().rstrip().lower()
    ret_name = "_".join(ret_name.split())
    return ret_name


def verify_dir_structure(path: str, dir_structure: dict):
    """Verify that given path complies to given directory structure.
    Raises:
        VerifyPathException
    """
    for item, subitem in dir_structure.items():
        if isinstance(subitem, str) and subitem == "file":
            filename = os.path.join(path, item)
            if not os.path.isfile(filename):
                if os.path.exists(filename):
                    raise VerifyPathException(f"{filename} is not a regular file")
                else:
                    raise VerifyPathException(f"File {filename} not found")
        elif item is Device:
            for hostname in os.listdir(path):
                hostname_path = os.path.join(path, hostname)
                if not os.path.isdir(hostname_path) or hostname.startswith("."):
                    continue
                if not Device.valid_hostname(hostname):
                    continue
                verify_dir_structure(hostname_path, subitem)
        elif isinstance(item, str) and item == "group":
            for groupname in os.listdir(path):
                groupname_path = os.path.join(path, groupname)
                if not os.path.isdir(groupname_path) or groupname.startswith("."):
                    continue
                if groupname not in get_groups():
                    continue
                verify_dir_structure(groupname_path, subitem)
        else:
            dirname = os.path.join(path, item)
            if not os.path.isdir(dirname):
                if os.path.exists(dirname):
                    raise VerifyPathException(f"{dirname} is not a directory")
                else:
                    raise VerifyPathException(f"Directory {dirname} not found")

            if subitem:
                verify_dir_structure(os.path.join(path, item), dir_structure[item])


def keys_exists(multi_dict: dict, keys: List[str]) -> bool:
    """Check if multi-level dict has specific keys"""
    _multi_dict = multi_dict
    for key in keys:
        try:
            _multi_dict = _multi_dict[key]
        except KeyError:
            return False
    return True


def get_setting_filename(repo_root: str, path: List[str]) -> str:
    """Check that the setting filename is defined in DIR_STRUCTURE and
    if so return a proper os path to the setting file.

    Args:
        repo_root: repository root directory
        path: a list containing all parts of filename to append after repo_root
    Raises:
        ValueError
    """
    if not path or not isinstance(path, list):
        raise ValueError("Empty path list received")
    if path[0] == "devices":
        if not len(path) >= 3:
            raise ValueError("Invalid directory structure for devices settings")
        if not keys_exists(DIR_STRUCTURE_HOST, path[2:]):
            raise ValueError("File {} not defined in DIR_STRUCTURE".format(path[2:]))
    elif path[0] == "groups":
        if not len(path) >= 3:
            raise ValueError("Invalid directory structure for groups settings")
        if not keys_exists(DIR_STRUCTURE_HOST, path[2:]):
            raise ValueError("File {} not defined in DIR_STRUCTURE".format(path[2:]))
    elif re.match(MODEL_IF_REGEX, path[1]):
        pass
    elif not keys_exists(DIR_STRUCTURE, path):
        raise ValueError("File {} not defined in DIR_STRUCTURE".format(path))
    return os.path.join(repo_root, *path)


def get_pydantic_error_value(data: dict, loc: tuple):
    """Get the actual value that caused the error in pydantic"""
    try:
        obj = data
        for item in loc:
            if type(obj) is str:
                return obj
            obj = obj[item]
    except KeyError:
        return None
    else:
        return obj


def get_pydantic_field_descr(schema: dict, loc: tuple):
    """Get the description from a pydantic Field definition based on a model
    schema and a "loc" tuple from pydantic ValidatorError.errors()"""
    next_schema = None
    for loc_part in loc:
        if next_schema and "$ref" in next_schema:
            ref_to = next_schema["$ref"].split("/")[2]
            next_schema = schema["definitions"][ref_to]["properties"][loc_part]
        elif next_schema:
            if type(loc_part) is int:
                next_schema = next_schema["items"]
            else:
                next_schema = schema["definitions"][next_schema]["properties"][loc_part]
        else:
            next_schema = schema["properties"][loc_part]
    if "description" in next_schema:
        return next_schema["description"]
    else:
        return None


def check_settings_syntax(settings_dict: dict, settings_metadata_dict: dict) -> dict:
    """Verify settings syntax and return a somewhat helpful error message.

    Raises:
        SettingsSyntaxError
    """
    logger = get_logger()
    try:
        ret_dict = f_root(**settings_dict).model_dump()
    except ValidationError as validation_error:
        msg = ""
        for num, error in enumerate(validation_error.errors()):
            # If there are two errors and the last one is of type none allowed
            # then skip recording the second error because it's an implication
            # of the first error (the value has to be correct or none)
            # TODO: handle multiple occurrences of this?
            if len(validation_error.errors()) == 2 and num == 1 and error["type"] == "type_error.none.allowed":
                continue
            # TODO: Find a way to present customised error message when string
            # regex match fails instead of just showing the regex pattern.
            loc = error["loc"]
            origin = "unknown"
            if loc[0] in settings_metadata_dict:
                origin = settings_metadata_dict[loc[0]]
            error_msg = "Validation error for setting {}, bad value: {} (value origin: {})\n".format(
                "->".join(str(x) for x in loc), get_pydantic_error_value(settings_dict, loc), origin
            )
            try:
                pydantic_descr = get_pydantic_field_descr(f_root.model_json_schema(), loc)
                if pydantic_descr:
                    pydantic_descr_msg = ", field should be: {}".format(pydantic_descr)
                else:
                    pydantic_descr_msg = ""
            except Exception as descr_error:
                logger.debug(descr_error)
                pydantic_descr_msg = ""
            error_msg += "Message: {}{}\n".format(error["msg"], pydantic_descr_msg)
            msg += error_msg
        raise SettingsSyntaxError(msg)
    else:
        return ret_dict


def sizeof_fmt(num, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def check_settings_collisions(unique_vlans: bool = True):
    """Check settings for any duplicates/collisions.
    This will call get_settings on all devices so make sure to not call this
    from get_settings.

    Args:
        unique_vlans: If enabled VLANs has to be globally unique

    Returns:

    """
    logger = get_logger()
    mgmt_vlans: Set[int] = set()
    devices_dict: dict[str, dict] = {}
    with sqla_session() as session:
        mgmtdoms = session.query(Mgmtdomain).all()
        for mgmtdom in mgmtdoms:
            if mgmtdom.vlan and isinstance(mgmtdom.vlan, int):
                if unique_vlans and mgmtdom.vlan in mgmt_vlans:
                    raise VlanConflictError(
                        "Management VLAN {} used in multiple management domains".format(mgmtdom.vlan)
                    )
                mgmt_vlans.add(mgmtdom.vlan)
        managed_devices: List[Device] = session.query(Device).filter(Device.state == DeviceState.MANAGED).all()
        for dev in managed_devices:
            dev_settings, _ = get_settings(dev.hostname, dev.device_type)
            devices_dict[dev.hostname] = dev_settings

    logger.debug("Memory size of all device settings: {}".format(sizeof_fmt(json.dumps(devices_dict).__sizeof__())))

    check_vlan_collisions(devices_dict, mgmt_vlans, unique_vlans)
    check_group_priority_collisions()


def get_internal_vlan_range(settings) -> range:
    if "internal_vlans" not in settings or not isinstance(settings["internal_vlans"], dict):
        return range(0)
    if (
        "vlan_id_low" in settings["internal_vlans"]
        and "vlan_id_high" in settings["internal_vlans"]
        and type(settings["internal_vlans"]["vlan_id_low"]) is int
        and type(settings["internal_vlans"]["vlan_id_high"]) is int
    ):
        return range(settings["internal_vlans"]["vlan_id_low"], settings["internal_vlans"]["vlan_id_high"] + 1)
    else:
        return range(0)


def check_vlan_collisions(devices_dict: Dict[str, dict], mgmt_vlans: Set[int], unique_vlans: bool = True):
    logger = get_logger()
    # save global VLAN IDs and their unique vxlan name
    global_vlans: dict[int, str] = dict.fromkeys(mgmt_vlans, "management")
    global_vnis: dict[int, str] = {}
    device_vlan_ids: dict[str, Set[int]] = {}  # save used VLAN IDs per device
    device_vlan_names: dict[str, Set[str]] = {}  # save used VLAN names per device
    access_hostnames: List[str] = []
    with sqla_session() as session:
        access_devs = session.query(Device).filter(Device.device_type == DeviceType.ACCESS).all()
        for dev in access_devs:
            access_hostnames.append(dev.hostname)

    for hostname, settings in devices_dict.items():
        if "vxlans" not in settings:
            continue
        for vxlan_name, vxlan_data in settings["vxlans"].items():
            # VXLAN VNI checks
            if "vni" not in vxlan_data or not isinstance(vxlan_data["vni"], int):
                logger.error("VXLAN {} is missing vni".format(vxlan_name))
                continue
            if vxlan_data["vni"] in global_vnis and global_vnis[vxlan_data["vni"]] != vxlan_name:
                raise VlanConflictError(
                    "VXLAN VNI {} used in VXLAN {} is already used elsewhere".format(vxlan_data["vni"], vxlan_name)
                )
            elif vxlan_data["vni"] not in global_vnis:
                global_vnis[vxlan_data["vni"]] = vxlan_name
            # VLAN id checks
            if "vlan_id" not in vxlan_data or not isinstance(vxlan_data["vlan_id"], int):
                logger.error("VXLAN {} is missing vlan_id".format(vxlan_name))
                continue
            if (
                unique_vlans
                and vxlan_data["vlan_id"] in global_vlans
                and global_vlans[vxlan_data["vlan_id"]] != vxlan_name
            ):
                raise VlanConflictError(
                    "VLAN id {} used in VXLAN {} is already used elsewhere".format(vxlan_data["vlan_id"], vxlan_name)
                )
            elif hostname in device_vlan_ids and vxlan_data["vlan_id"] in device_vlan_ids[hostname]:
                raise VlanConflictError(
                    "VLAN id {} used multiple times in device {}".format(vxlan_data["vlan_id"], hostname)
                )
            elif hostname in device_vlan_ids:
                device_vlan_ids[hostname].add(vxlan_data["vlan_id"])
            else:
                device_vlan_ids[hostname] = {vxlan_data["vlan_id"]}
            if vxlan_data["vlan_id"] in get_internal_vlan_range(settings):
                raise VlanConflictError(
                    "VLAN id {} is overlapping with internal VLAN range".format(vxlan_data["vlan_id"])
                )
            global_vlans[vxlan_data["vlan_id"]] = vxlan_name
            # VLAN name checks
            if "vlan_name" not in vxlan_data or not isinstance(vxlan_data["vlan_name"], str):
                logger.error("VXLAN {} is missing vlan_name".format(vxlan_name))
                continue
            if (
                hostname in device_vlan_names
                and vxlan_data["vlan_name"] in device_vlan_names[hostname]
                and hostname in access_hostnames
            ):  # only trigger for access switches
                raise VlanConflictError(
                    "VLAN name {} used multiple times in device {}".format(vxlan_data["vlan_name"], hostname)
                )
            elif hostname in device_vlan_names:
                device_vlan_names[hostname].add(vxlan_data["vlan_name"])
            else:
                device_vlan_names[hostname] = {vxlan_data["vlan_name"]}


def check_group_priority_collisions(settings: Optional[dict] = None):
    priorities: Dict[int, str] = {}
    if not settings:
        settings, _ = get_group_settings()
    if not settings:
        return
    if not settings.get("groups", None):
        return
    for group in settings["groups"]:
        if "name" not in group["group"]:
            continue
        if "group_priority" not in group["group"] or group["group"]["group_priority"] == 0:
            continue
        if group["group"]["group_priority"] in priorities.keys():
            raise ValueError(
                "Groups must have unique group_priority values, "
                "but group {} and {} both have priority {}".format(
                    priorities[group["group"]["group_priority"]],
                    group["group"]["name"],
                    group["group"]["group_priority"],
                )
            )
        priorities[group["group"]["group_priority"]] = group["group"]["name"]


@redis_lru_cache
def read_settings_file(filename):
    with open(filename, "r") as f:
        return yaml.safe_load(f)


def read_settings(
    local_repo_path: str,
    path: List[str],
    origin: str,
    merged_settings,
    merged_settings_origin,
    groups: List[str] = None,
    hostname: str = None,
) -> Tuple[dict, dict]:
    """

    Args:
        local_repo_path: Local path to settings repository
        path: Path to look for inside repo
        origin: What to name call this origin
        merged_settings: Existing settings
        merged_settings_origin: Existing settings origin info
        groups: Optional list of groups to filter on (using filter_yamldata)
        hostname: Optional hostname to filter on (using filter_yamldata)

    Returns:
        merged_settings, merged_settings_origin
    """
    logger = get_logger()
    filename = get_setting_filename(local_repo_path, path)
    yamldata = read_settings_file(filename)
    if not yamldata:
        return merged_settings, merged_settings_origin
    elif not isinstance(yamldata, dict):
        logger.info("Invalid yaml file ignored: {}".format(filename))
        return merged_settings, merged_settings_origin
    settings: dict = yamldata
    if groups or hostname:
        syntax_dict, syntax_dict_origin = merge_dict_origin({}, settings, {}, origin)
        check_settings_syntax(syntax_dict, syntax_dict_origin)
        settings = filter_yamldata(settings, groups, hostname)
    return merge_dict_origin(merged_settings, settings, merged_settings_origin, origin)


def filter_yamldata(data: Union[List, dict], groups: List[str], hostname: str, recdepth=100) -> Union[List, dict]:
    """Filter data and remove dictionary items if they have a key that specifies
    a list of groups, but none of those groups are included in the groups argument.
    Should only be called with yaml.safe_load:ed data.

    Args:
        data: yaml safe_load:ed data
        groups: a list of groups to filter on
        hostname: a hostname to filter on
        recdepth: recursion depth limit, default 100

    Returns:
        filtered data
    """
    if recdepth < 1:
        return data
    elif isinstance(data, list):
        ret_l = []
        for item in data:
            f_item = filter_yamldata(item, groups, hostname, recdepth - 1)
            if f_item:
                ret_l.append(f_item)
        return ret_l
    elif isinstance(data, dict):
        ret_d = {}
        group_match = False
        hostname_match = False
        do_filter_group = False
        do_filter_hostname = False
        for k, v in data.items():
            if not v:
                ret_d[k] = v
                continue
            if k == "groups":
                if not isinstance(v, list):  # Should already be checked by pydantic now
                    raise SettingsSyntaxError(
                        "Groups field must be a list or empty (currently {}) in: {}".format(type(v).__name__, data)
                    )
                do_filter_group = True
                ret_d[k] = v
                for group in v:
                    if group in groups:
                        group_match = True
            elif k == "devices":
                if not isinstance(v, list):  # Should already be checked by pydantic now
                    raise SettingsSyntaxError(
                        "Devices field must be a list or empty (currently {}) in: {}".format(type(v).__name__, data)
                    )
                do_filter_hostname = True
                ret_d[k] = v
                if hostname in v:
                    hostname_match = True
            else:
                ret_v = filter_yamldata(v, groups, hostname, recdepth - 1)
                if ret_v:
                    ret_d[k] = ret_v
        if (do_filter_group or do_filter_hostname) and not group_match and not hostname_match:
            return None
        else:
            return ret_d
    else:
        return data


def get_downstream_dependencies(hostname: str, settings: dict) -> dict:
    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            return settings
        if dev.device_type != DeviceType.DIST:
            return settings
        neighbor_devices = dev.get_neighbors(session)
        # Downstream device hostnames
        ds_hostnames = []
        for neighbor_dev in neighbor_devices:
            if neighbor_dev.device_type == DeviceType.ACCESS:
                ds_hostnames.append(neighbor_dev.hostname)
        for ds_hostname in ds_hostnames:
            ds_settings, _ = get_settings(ds_hostname, DeviceType.ACCESS)
            for vxlan_name, vxlan_data in ds_settings["vxlans"].items():
                if vxlan_name not in settings["vxlans"].keys():
                    settings["vxlans"][vxlan_name] = vxlan_data
    return settings


@redis_lru_cache
def get_settings(
    hostname: Optional[str] = None, device_type: Optional[DeviceType] = None, device_model: Optional[str] = None
) -> Tuple[dict, dict]:
    """Get settings to use for device matching hostname or global
    settings if no hostname is specified."""
    logger = get_logger()
    get_type = "global"

    local_repo_path = app_settings.SETTINGS_LOCAL
    try:
        verify_dir_structure(local_repo_path, DIR_STRUCTURE)
    except VerifyPathException as e:
        logger.exception("Exception when verifying settings repository directory structure")
        raise e

    # 1. Get CNaaS-NMS default settings
    data_dir = pkg_resources.resource_filename(__name__, "data")
    with open(os.path.join(data_dir, "default_settings.yml"), "r") as f_default_settings:
        settings: dict = yaml.safe_load(f_default_settings)

    settings_origin = {}
    for k in settings.keys():
        settings_origin[k] = "default"

    # 2. Get settings repo global settings
    if hostname:
        # Some settings parsing require knowledge of group memberships
        groups = get_groups(hostname)
        settings, settings_origin = read_settings(
            local_repo_path, ["global", "base_system.yml"], "global->base_system.yml", settings, settings_origin, groups
        )
    else:
        settings, settings_origin = read_settings(
            local_repo_path, ["global", "base_system.yml"], "global->base_system.yml", settings, settings_origin
        )

    # 3. Get settings from special fabric classification (dist + core)
    if device_type and (device_type == DeviceType.DIST or device_type == DeviceType.CORE):
        settings, settings_origin = read_settings(
            local_repo_path, ["fabric", "base_system.yml"], "fabric->base_system.yml", settings, settings_origin
        )
    # 4. Get settings repo device type settings
    if device_type:
        get_type = "devicetype {}".format(device_type.name)
        if device_type == DeviceType.UNKNOWN:
            if hostname is None:
                raise ValueError("It's not possible to get settings for devices with type UNKNOWN")
            else:
                logger.warning("Device type is UNKNOWN, trying to get settings for hostname {}".format(hostname))
        else:
            settings, settings_origin = read_settings(
                local_repo_path,
                [device_type.name.lower(), "base_system.yml"],
                "devicetype->base_system.yml",
                settings,
                settings_origin,
            )
    if hostname:
        get_type = "hostname {}".format(hostname)
        settings, settings_origin = read_settings(
            local_repo_path, ["global", "routing.yml"], "global->routing.yml", settings, settings_origin, groups
        )
        settings, settings_origin = read_settings(
            local_repo_path, ["global", "vxlans.yml"], "global->vxlans.yml", settings, settings_origin, groups, hostname
        )
        settings = get_downstream_dependencies(hostname, settings)
        # 5. Get settings repo group specific settings
        primary_group = get_device_primary_groups().get(hostname)
        if primary_group:
            # add templates worktree
            templates_branch = get_group_templates_branch(primary_group)
            if templates_branch:
                refresh_templates_worktree(templates_branch)
            if os.path.isdir(os.path.join(local_repo_path, "groups", primary_group)):
                settings, settings_origin = read_settings(
                    local_repo_path,
                    ["groups", primary_group, "base_system.yml"],
                    "groups->{}->base_system.yml".format(primary_group),
                    settings,
                    settings_origin,
                )
                settings, settings_origin = read_settings(
                    local_repo_path,
                    ["groups", primary_group, "interfaces.yml"],
                    "groups->{}->base_system.yml".format(primary_group),
                    settings,
                    settings_origin,
                )
                settings, settings_origin = read_settings(
                    local_repo_path,
                    ["groups", primary_group, "routing.yml"],
                    "groups->{}->base_system.yml".format(primary_group),
                    settings,
                    settings_origin,
                )
        # 6. Get settings repo device specific settings
        if os.path.isdir(os.path.join(local_repo_path, "devices", hostname)):
            settings, settings_origin = read_settings(
                local_repo_path,
                ["devices", hostname, "base_system.yml"],
                "device->{}->base_system.yml".format(hostname),
                settings,
                settings_origin,
            )
            settings, settings_origin = read_settings(
                local_repo_path,
                ["devices", hostname, "interfaces.yml"],
                "device->{}->interfaces.yml".format(hostname),
                settings,
                settings_origin,
            )
            settings, settings_origin = read_settings(
                local_repo_path,
                ["devices", hostname, "routing.yml"],
                "device->{}->routing.yml".format(hostname),
                settings,
                settings_origin,
                groups,
            )
        # Check for model specific default interface settings
        elif (
            (device_type == DeviceType.DIST or device_type == DeviceType.CORE)
            and device_type
            and device_model
            and os.path.isfile(
                os.path.join(
                    local_repo_path,
                    device_type.name.lower(),
                    "interfaces_{}.yml".format(model_name_sanitize(device_model)),
                )
            )
        ):
            settings, settings_origin = read_settings(
                local_repo_path,
                [device_type.name.lower(), "interfaces_{}.yml".format(device_model.lower())],
                "{}->interfaces_{}.yml".format(device_type.name.lower(), model_name_sanitize(device_model)),
                settings,
                settings_origin,
            )

    else:
        # Some settings parsing require knowledge of group memberships
        groups = []
        settings, settings_origin = read_settings(
            local_repo_path, ["global", "routing.yml"], "global->routing.yml", settings, settings_origin, groups
        )
        settings, settings_origin = read_settings(
            local_repo_path, ["global", "vxlans.yml"], "global->vxlans.yml", settings, settings_origin, groups, hostname
        )
    # Verify syntax
    verified_settings = check_settings_syntax(settings, settings_origin)
    set_everything = set(settings)
    set_model = set(verified_settings)
    diff_model = set_everything - set_model
    if diff_model:
        logger.warn(
            "Some configured settings for {} are undefined in model: {}".format(get_type, set_everything - set_model)
        )
    return verified_settings, settings_origin


@redis_lru_cache
def get_group_settings() -> Tuple[dict, dict]:
    logger = get_logger()
    settings: dict = {}
    settings_origin: dict = {}

    local_repo_path = app_settings.SETTINGS_LOCAL
    try:
        verify_dir_structure(os.path.join(local_repo_path, "global"), DIR_STRUCTURE["global"])
    except VerifyPathException as e:
        logger.exception("Exception when verifying settings repository directory structure")
        raise e

    data_dir = pkg_resources.resource_filename(__name__, "data")
    with open(os.path.join(data_dir, "default_groups.yml"), "r") as f_default_settings:
        default_settings: dict = yaml.safe_load(f_default_settings)

    settings, settings_origin = read_settings(
        local_repo_path, ["global", "groups.yml"], "global", settings, settings_origin
    )
    settings["groups"] += default_settings["groups"]
    check_settings_syntax(settings, settings_origin)
    return f_groups(**settings).model_dump(), settings_origin


@redis_lru_cache
def get_groups(hostname: Optional[str] = None) -> List[str]:
    """Return list of names for valid groups."""
    groups = []
    settings, origin = get_group_settings()
    if not settings:
        return groups
    if not settings.get("groups", None):
        return groups
    for group in settings["groups"]:
        if "name" not in group["group"]:
            continue
        if hostname:
            if "regex" not in group["group"]:
                continue
            # TODO: try and catch, report what regex failed
            if not re.match(group["group"]["regex"], hostname):
                continue
        groups.append(group["group"]["name"])
    return groups


def get_group_regex(group_name: str) -> Optional[str]:
    """Returns a string containing the regex defining the specified
    group name if it's found."""
    return get_group_settings_asdict().get(group_name, {}).get("regex")


def get_group_templates_branch(group_name: str) -> Optional[str]:
    """Returns a string containing the regex defining the specified
    group name if it's found."""
    return get_group_settings_asdict().get(group_name, {}).get("templates_branch")


@redis_lru_cache
def get_group_settings_asdict() -> Dict[str, Dict[str, Any]]:
    """Returns a dict with group name as key and other parameters as values"""
    settings, _ = get_group_settings()
    if not settings:
        return {}
    if not settings.get("groups"):
        return {}
    group_dict: Dict[str, Dict[str, Any]] = {}
    for group in settings["groups"]:
        if "name" not in group["group"]:
            continue
        group_dict[group["group"]["name"]] = group["group"]
        del group_dict[group["group"]["name"]]["name"]
    return group_dict


def get_groups_priorities(hostname: Optional[str] = None, settings: Optional[dict] = None) -> Dict[str, int]:
    """Return dicts with {name: priority} for groups"""
    groups_priorities = {}

    if not settings:
        settings, _ = get_group_settings()
    if not settings:
        return groups_priorities
    if not settings.get("groups", None):
        return groups_priorities
    for group in settings["groups"]:
        if "name" not in group["group"]:
            continue
        if "group_priority" not in group["group"] or group["group"]["group_priority"] == 0:
            continue
        if hostname:
            if "regex" not in group["group"]:
                continue
            # TODO: try and catch, report what regex failed
            if not re.match(group["group"]["regex"], hostname):
                continue
        groups_priorities[group["group"]["name"]] = group["group"]["group_priority"]
    return groups_priorities


def get_groups_priorities_sorted(hostname: Optional[str] = None, settings: Optional[dict] = None) -> Dict[str, int]:
    return {
        k: v
        for k, v in sorted(
            get_groups_priorities(hostname, settings).items(),
            key=lambda item: item[1],  # sort on value(priority)
            reverse=True,
        )
    }  # sort highest priority first


def find_primary_group(secondary_groups: list, groups_priorities_sorted: Dict[str, int]) -> str:
    for prio_group in groups_priorities_sorted.keys():
        for sec_group in secondary_groups:
            if prio_group == sec_group:
                return prio_group
    return "DEFAULT"


def parse_device_primary_groups() -> Dict[str, str]:
    """Returns a dict with {hostname: primary_group} from settings"""
    groups_priorities_sorted = get_groups_priorities_sorted()
    device_primary_group: Dict[str, str] = {}
    with sqla_session() as session:
        devices: List[Device] = session.query(Device).all()
        for dev in devices:
            groups = get_groups(dev.hostname)
            primary_group: str = find_primary_group(groups, groups_priorities_sorted)
            device_primary_group[dev.hostname] = primary_group
    return device_primary_group


def update_device_primary_groups():
    device_primary_group = parse_device_primary_groups()
    if not device_primary_group:
        return
    with redis_session() as redis:
        redis.hset("device_primary_group", mapping=device_primary_group)


def get_device_primary_groups(no_cache: bool = False) -> Dict[str, str]:
    """Returns a dict with {hostname: primary_group} from redis

    Args:
        no_cache: Update redis cache before returning data
    """
    logger = get_logger()
    # update redis if redis is empty
    with redis_session() as redis:
        if not redis.exists("device_primary_group"):
            update_device_primary_groups()
    if no_cache:
        update_device_primary_groups()
    device_primary_group: dict = {}
    with redis_session() as redis:
        try:
            device_primary_group = redis.hgetall("device_primary_group")
        except Exception as e:
            logger.exception("Error while getting device_primary_group from redis: {} ".format(e))
    return device_primary_group


def rebuild_settings_cache() -> None:
    """Clear cache and rebuild for devicetypes.

    Raises:
        SettingsSyntaxError: Syntax is wrong in settings files
        VlanConflictError: Multiple conflicting VLANs exists on same device
    """
    logger = get_logger()
    logger.debug("Clearing redis-lru cache for settings")
    with redis_session() as redis_db:
        mem_stats_before = redis_db.memory_stats()
        cache = RedisLRU(redis_db)
        cache.clear_all_cache()
        mem_stats_after = redis_db.memory_stats()
        try:
            logger.debug(
                "Redis allocated before: {} ({} keys), after: {} ({} keys)".format(
                    sizeof_fmt(mem_stats_before["total.allocated"]),
                    mem_stats_before["keys.count"],
                    sizeof_fmt(mem_stats_after["total.allocated"]),
                    mem_stats_after["keys.count"],
                )
            )
        except Exception:
            pass
    logger.debug("Rebuilding settings cache for global settings and primary groups")
    update_device_primary_groups()
    get_settings()
    test_devtypes = [DeviceType.ACCESS, DeviceType.DIST, DeviceType.CORE]
    logger.debug("Rebuilding settings cache for devicetypes")
    for devtype in test_devtypes:
        get_settings(device_type=devtype)
    logger.debug("Rebuilding settings cache for device specific settings")
    with sqla_session() as session:
        for hostname in os.listdir(os.path.join(app_settings.SETTINGS_LOCAL, "devices")):
            hostname_path = os.path.join(app_settings.SETTINGS_LOCAL, "devices", hostname)
            if not os.path.isdir(hostname_path) or hostname.startswith("."):
                continue
            if not Device.valid_hostname(hostname):
                continue
            dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
            if dev is None or dev.device_type == DeviceType.UNKNOWN:
                logger.warning(f"Device {hostname} specified in settings/devices but it was not found in database")
                continue
            get_settings(hostname, dev.device_type)
    logger.debug("Rebuilding settings cache for device models")
    for devtype_str, device_models in get_model_specific_configfiles(True).items():
        devtype = DeviceType[devtype_str]
        for device_model in device_models:
            get_settings("nonexisting", devtype, device_model)
    logger.debug("Rechecking settings collisions")
    check_settings_collisions(api_settings.GLOBAL_UNIQUE_VLANS)
