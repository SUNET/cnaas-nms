import hashlib
import importlib
import json
import logging
import os
import re
import types
from ipaddress import ip_interface
from pathlib import Path
from typing import Any, Dict, Iterator, List, Literal, Optional, Set, Tuple, Union, overload

import jmespath
from absl import logging as absl_logging
from aerleon.aclgen import Error as ACLGenError
from aerleon.api import Generate
from aerleon.lib import naming
from aerleon.lib.policy_builder import PolicyDict, PolicyFilter, PolicyFilterTermsOnly, TermsList
from aerleon.lib.yaml import PolicyTypeError
from netutils.lib_mapper import AERLEON_LIB_MAPPER, AERLEON_LIB_MAPPER_REVERSE, NAPALM_LIB_MAPPER
from pydantic import BaseModel, ValidationError
from redis import StrictRedis
from redis_lru import RedisLRU
from sqlalchemy import inspect
from sqlalchemy.exc import NoInspectionAvailable

from cnaas_nms.app_settings import api_settings, app_settings
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.git_worktrees import refresh_templates_worktree
from cnaas_nms.db.mgmtdomain import Mgmtdomain
from cnaas_nms.db.session import redis_session, sqla_session
from cnaas_nms.db.settings_fields import (
    f_access_list,
    f_group,
    f_group_device_filter,
    f_groups,
)
from cnaas_nms.db.settings_fields import (
    f_access_lists as f_access_lists_model,
)
from cnaas_nms.db.settings_fields import (
    f_base_system as f_base_system_model,
)
from cnaas_nms.db.settings_fields import (
    f_interfaces as f_interfaces_model,
)
from cnaas_nms.db.settings_fields import (
    f_routing as f_routing_model,
)
from cnaas_nms.db.settings_fields import f_vxlans as f_vxlans_model
from cnaas_nms.tools.log import CaptureHandler, get_logger
from cnaas_nms.tools.mergedict import merge_dict_origin
from cnaas_nms.tools.yaml import yaml_safe_load


@overload
def get_settings_model(model: Literal["f_access_lists"]) -> type[f_access_lists_model]: ...
@overload
def get_settings_model(model: Literal["f_base_system"]) -> type[f_base_system_model]: ...
@overload
def get_settings_model(model: Literal["f_interfaces"]) -> type[f_interfaces_model]: ...
@overload
def get_settings_model(model: Literal["f_routing"]) -> type[f_routing_model]: ...
@overload
def get_settings_model(model: Literal["f_vxlans"]) -> type[f_vxlans_model]: ...
def get_settings_model(
    model: str,
) -> type[BaseModel]:
    logger = get_logger()

    valid_models = ["f_access_lists", "f_base_system", "f_interfaces", "f_routing", "f_vxlans"]

    if model not in valid_models:
        logger.error(f"Model: '{model}' is not valid, valid options: {valid_models}")
        raise ValueError(f"Invalid model '{model}'. Valid options are: {valid_models}")

    try:
        settings_fields_path = os.getenv("PLUGIN_SETTINGS_FIELDS_MODULE", "cnaas_nms.plugins.settings_fields")
        settings_fields = importlib.import_module(settings_fields_path)
        f_setting_ret = getattr(settings_fields, model)
        logger.debug("Loaded settings_fields module from plugin: {}".format(settings_fields_path))
    except ModuleNotFoundError:
        f_setting_ret = getattr(importlib.import_module("cnaas_nms.db.settings_fields"), model)
        logger.debug("Loaded settings_fields module from bundled cnaas-nms")
    except Exception as e:
        logger.error("Unable to load plugin module for settings_fields: {}".format(e))
        f_setting_ret = getattr(importlib.import_module("cnaas_nms.db.settings_fields"), model)
    return f_setting_ret


f_access_lists = get_settings_model("f_access_lists")
f_base_system = get_settings_model("f_base_system")
f_interfaces = get_settings_model("f_interfaces")
f_routing = get_settings_model("f_routing")
f_vxlans = get_settings_model("f_vxlans")


class f_root(
    f_access_lists,  # type: ignore
    f_base_system,  # type: ignore
    f_interfaces,  # type: ignore
    f_routing,  # type: ignore
    f_vxlans,  # type: ignore
):
    pass


redis_client = StrictRedis(
    host=app_settings.REDIS_HOSTNAME,
    port=app_settings.REDIS_PORT,
    retry_on_timeout=True,
    socket_keepalive=True,
)

_DEVICE_FILTER_FIELDS = frozenset(f_group_device_filter.model_fields)


def _make_hashable(obj: Any) -> Any:
    """Recursively convert objects into hashable objects."""
    if type(obj) in (int, str, float, bool, type(None)):
        return obj

    elif isinstance(obj, dict):
        return tuple((k, _make_hashable(obj[k])) for k in sorted(obj))

    elif isinstance(obj, (list, tuple)):
        return tuple(_make_hashable(v) for v in obj)

    elif isinstance(obj, set):
        # Sets must be sorted to guarantee stable representations across runs
        try:
            return tuple(sorted(_make_hashable(v) for v in obj))
        except TypeError:
            # Fallback if set contains mixed, unorderable types
            return frozenset(_make_hashable(v) for v in obj)

    elif isinstance(obj, Device):
        # If device use only the fields that are relevant
        device_dict = obj.as_dict()
        return tuple((k, _make_hashable(device_dict[k])) for k in sorted(device_dict) if k in _DEVICE_FILTER_FIELDS)

    elif isinstance(obj, (naming.Naming, naming._ItemUnit)):
        return tuple((k, _make_hashable(obj.__dict__[k])) for k in sorted(obj.__dict__))

    elif hasattr(obj, "as_dict"):
        obj_dict = obj.as_dict()
        return tuple((k, _make_hashable(obj_dict[k])) for k in sorted(obj_dict))

    return obj


class NMSRedisLRU(RedisLRU):
    def _decorator_key(self, func: types.FunctionType, *args, **kwargs):
        """
        Generate a hashable cache key for RedisLRU,
        even when passing dicts, lists, sets, or custom objects.
        """
        # Convert args & kwargs into stable, hashable forms
        safe_args = tuple(_make_hashable(arg) for arg in args)
        safe_kwargs = tuple((k, _make_hashable(v)) for k, v in sorted(kwargs.items()))

        raw_key_data = f"{safe_args!r}:{safe_kwargs!r}"

        # We want a fast hash here, don't care about a secure one.
        # We hash the string so it is not too long for redis to handle.
        # Shorter keys in redis improves performance and reduces memory usage.
        # Encode only the args and kwargs
        hashed_args = hashlib.md5(raw_key_data.encode("utf-8")).hexdigest()  # noqa: S4790

        return f"{self.key_prefix}:{func.__module__}:{func.__qualname__}:{hashed_args}"


redis_lru_cache = NMSRedisLRU(redis_client, default_ttl=24 * 3600)


class VerifyPathException(Exception):
    pass


class SettingsSyntaxError(Exception):
    pass


class VlanConflictError(Exception):
    pass


class AccessListGenerationError(Exception):
    pass


DIR_STRUCTURE_HOST = {
    "base_system.yml": "file",
    "interfaces.yml": "file",
    "routing.yml": "file",
}

DIR_STRUCTURE: dict[str, Any] = {
    "global": {
        "access_lists.yml": "optional_file",
        "base_system.yml": "file",
        "groups.yml": "file",
        "routing.yml": "file",
        "vxlans.yml": "file",
    },
    "fabric": {"base_system.yml": "file"},
    "firewall": {"base_system.yml": "file"},
    "core": {"base_system.yml": "file"},
    "dist": {"base_system.yml": "file"},
    "access": {"base_system.yml": "file"},
    "devices": {Device: DIR_STRUCTURE_HOST},
    "groups": {"group": DIR_STRUCTURE_HOST},
}

FILE_MODEL_MAP: dict[str, type[BaseModel]] = {
    "access_lists.yml": f_access_lists,
    "base_system.yml": f_base_system,
    "groups.yml": f_groups,
    "interfaces.yml": f_interfaces,
    "routing.yml": f_routing,
    "vxlans.yml": f_vxlans,
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
    ret: dict[str, List[str]] = {"CORE": [], "DIST": []}
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
        elif isinstance(subitem, str) and subitem == "optional_file":
            filename = os.path.join(path, item)
            if not os.path.isfile(filename) and os.path.exists(filename):
                raise VerifyPathException(f"{filename} is not a regular file")
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
    next_schema: Optional[dict[str, Any]] = None
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
    if next_schema and "description" in next_schema:
        return next_schema["description"]
    else:
        return None


def check_system_access_lists(settings_dict: dict):
    """Raises SettingsSyntaxError"""
    acl_names = set(settings_dict.get("access_lists", {}).keys())
    for system_acl in settings_dict.get("system_access_lists", []):
        if system_acl not in acl_names:
            raise SettingsSyntaxError(f"System access list: {system_acl} must be defined as an access-list.")


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
                "->".join(str(x) for x in loc),
                get_pydantic_error_value(settings_dict, loc),
                origin,
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
    with sqla_session() as session:  # type: ignore
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
            dev_settings, _ = get_settings(dev, dev.device_type)
            devices_dict[dev.hostname] = dev_settings

    logger.debug("Memory size of all device settings: {}".format(sizeof_fmt(json.dumps(devices_dict).__sizeof__())))

    check_vlan_collisions(devices_dict, mgmt_vlans, unique_vlans)
    check_routing_policies(devices_dict)


def get_internal_vlan_range(settings) -> range:
    if "internal_vlans" not in settings or not isinstance(settings["internal_vlans"], dict):
        return range(0)
    if (
        "vlan_id_low" in settings["internal_vlans"]
        and "vlan_id_high" in settings["internal_vlans"]
        and type(settings["internal_vlans"]["vlan_id_low"]) is int
        and type(settings["internal_vlans"]["vlan_id_high"]) is int
    ):
        return range(
            settings["internal_vlans"]["vlan_id_low"],
            settings["internal_vlans"]["vlan_id_high"] + 1,
        )
    else:
        return range(0)


def check_bgp_neighbor_routemaps(hostname: str, vrfs: List, defined_policies: set[str]):
    for vrf in vrfs:
        for v4_neighbor in vrf["neighbor_v4"]:
            if v4_neighbor["route_map_in"] and v4_neighbor["route_map_in"] not in defined_policies:
                raise ValueError(f"{hostname}: BGP neighbor route map {v4_neighbor['route_map_in']} is not defined")
            if v4_neighbor["route_map_out"] and v4_neighbor["route_map_out"] not in defined_policies:
                raise ValueError(f"{hostname}: BGP neighbor route map {v4_neighbor['route_map_out']} is not defined")
        for v6_neighbor in vrf["neighbor_v6"]:
            if v6_neighbor["route_map_in"] and v6_neighbor["route_map_in"] not in defined_policies:
                raise ValueError(f"{hostname}: BGP neighbor route map {v6_neighbor['route_map_in']} is not defined")
            if v6_neighbor["route_map_out"] and v6_neighbor["route_map_out"] not in defined_policies:
                raise ValueError(f"{hostname}: BGP neighbor route map {v6_neighbor['route_map_out']} is not defined")


def check_routing_policies(devices_dict: Dict[str, dict]):
    # save global VLAN IDs and their unique vxlan name
    defined_policies = set()

    for hostname, settings in devices_dict.items():
        if "external_routing_policies" in settings:
            defined_policies.update(settings["external_routing_policies"])
        try:
            defined_policies.update(settings["routing_policies"].keys())
            check_bgp_neighbor_routemaps(hostname, settings["extroute_bgp"]["vrfs"], defined_policies)
        except (KeyError, TypeError):
            pass


def check_vlan_collisions(devices_dict: Dict[str, dict], mgmt_vlans: Set[int], unique_vlans: bool = True):
    logger = get_logger()
    # save global VLAN IDs and their unique vxlan name
    global_vlans: dict[int, str] = dict.fromkeys(mgmt_vlans, "management")
    global_vnis: dict[int, str] = {}
    device_vlan_ids: dict[str, Set[int]] = {}  # save used VLAN IDs per device
    device_vlan_names: dict[str, Set[str]] = {}  # save used VLAN names per device
    access_hostnames: List[str] = []
    with sqla_session() as session:  # type: ignore
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
            if "vxlan_vni_range" in settings and settings["vxlan_vni_range"]:
                vni_range = settings["vxlan_vni_range"].split("-")
                if not int(vni_range[0]) < vxlan_data["vni"] < int(vni_range[1]):
                    raise VlanConflictError(
                        "VXLAN VNI {} is outside of the allowed range {}".format(
                            vxlan_data["vni"], settings["vxlan_vni_range"]
                        )
                    )

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


@redis_lru_cache
def read_settings_file(filename):
    # Optional files that does not exists return nothing
    if not os.path.isfile(filename):
        return {}
    with open(filename, "r") as f:
        return yaml_safe_load(f)


def read_settings(
    local_repo_path: str,
    path: List[str],
    origin: str,
    merged_settings,
    merged_settings_origin,
    groups: Optional[List[str]] = None,
    hostname: Optional[str] = None,
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
    filepath = get_setting_filename(local_repo_path, path)
    filename = path[-1]
    yamldata = read_settings_file(filepath)
    if not yamldata:
        return merged_settings, merged_settings_origin
    elif not isinstance(yamldata, dict):
        logger.info("Invalid yaml file ignored: {}".format(filepath))
        return merged_settings, merged_settings_origin
    # Filter yamldata with the associated pydantic model and log any fields not meant in this file.
    # Defaults to f_root if the filename does not map to any specific model.
    f_model = FILE_MODEL_MAP.get(filename, f_root)
    # Check if there is any fields not meant to go in this file.
    invalid_keys = [key for key in yamldata if key not in f_model.model_fields]
    if invalid_keys:
        logger.error(
            "Invalid key(s) %s in settings file '%s' (path '%s'). Valid keys: %s. "
            "These keys will be ignored; please move these settings to the correct file.",
            ", ".join(sorted(invalid_keys)),
            filename,
            filepath,
            ", ".join(sorted(f_model.model_fields.keys())),
        )
    # Filter dict
    settings_from_file: dict = f_model.model_construct(**yamldata).model_dump(exclude_unset=True)
    if groups or hostname:
        syntax_dict, syntax_dict_origin = merge_dict_origin({}, settings_from_file, {}, origin)
        check_settings_syntax(syntax_dict, syntax_dict_origin)
        settings_from_file = filter_yamldata(settings_from_file, groups if groups else [], hostname if hostname else "")
    return merge_dict_origin(merged_settings, settings_from_file, merged_settings_origin, origin)


def filter_yamldata(data: Union[List, dict], groups: List[str], hostname: str) -> dict:
    logger = get_logger()
    filtered_yaml_data = recursive_filter_yamldata(data, groups, hostname)
    if not isinstance(filtered_yaml_data, dict):
        logger.info("Invalid yaml file ignored")
        return {}
    return filtered_yaml_data


def recursive_filter_yamldata_dictionary(
    data: dict, groups: List[str], hostname: str, recdepth=100
) -> Union[List, dict, None]:
    ret_d = {}
    group_match = False
    hostname_match = False
    do_filter_group = False
    do_filter_hostname = False
    for key, value in data.items():
        if not value:
            ret_d[key] = value
            continue
        if key == "groups":
            if not isinstance(value, list):  # Should already be checked by pydantic now
                raise SettingsSyntaxError(
                    "Groups field must be a list or empty (currently {}) in: {}".format(type(value).__name__, data)
                )
            do_filter_group = True
            ret_d[key] = value
            for group in value:
                if group in groups:
                    group_match = True
        elif key == "devices":
            if not isinstance(value, list):  # Should already be checked by pydantic now
                raise SettingsSyntaxError(
                    "Devices field must be a list or empty (currently {}) in: {}".format(type(value).__name__, data)
                )
            do_filter_hostname = True
            ret_d[key] = value
            if hostname in value:
                hostname_match = True
        else:
            ret_v = recursive_filter_yamldata(value, groups, hostname, recdepth - 1)
            if ret_v:
                ret_d[key] = ret_v
    if (do_filter_group or do_filter_hostname) and not group_match and not hostname_match:
        return None
    else:
        return ret_d


def recursive_filter_yamldata_list(
    data: List, groups: List[str], hostname: str, recdepth=100
) -> Union[List, dict, None]:
    ret_l = []
    for item in data:
        f_item = recursive_filter_yamldata(item, groups, hostname, recdepth - 1)
        if f_item:
            ret_l.append(f_item)
    return ret_l


def recursive_filter_yamldata(
    data: Union[List, dict], groups: List[str], hostname: str, recdepth=100
) -> Union[List, dict, None]:
    """Filter data and remove dictionary items if they have a key that specifies
    a list of groups, but none of those groups are included in the groups argument.
    Should only be called with yaml_safe_load:ed data.

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
        return recursive_filter_yamldata_list(data, groups, hostname, recdepth)
    elif isinstance(data, dict):
        return recursive_filter_yamldata_dictionary(data, groups, hostname, recdepth)
    else:
        return data


def get_downstream_dependencies(device: Device, settings: dict) -> dict:
    if device.device_type != DeviceType.DIST:
        return settings
    with sqla_session() as session:  # type: ignore
        neighbor_devices = device.get_neighbors(session)
        # Downstream device hostnames
        for neighbor_dev in neighbor_devices:
            if neighbor_dev.device_type != DeviceType.ACCESS:
                continue
            ds_settings, _ = get_settings(neighbor_dev, DeviceType.ACCESS)
            for vxlan_name, vxlan_data in ds_settings["vxlans"].items():
                if vxlan_name not in settings["vxlans"].keys():
                    settings["vxlans"][vxlan_name] = vxlan_data
    return settings


@redis_lru_cache
def get_settings(
    device: Optional[Device] = None,
    device_type: Optional[DeviceType] = None,
    device_model: Optional[str] = None,
) -> Tuple[dict, dict]:
    """Get settings to use for device matching hostname or global
    settings if no hostname is specified."""
    logger = get_logger()

    local_repo_path = app_settings.SETTINGS_LOCAL
    try:
        verify_dir_structure(local_repo_path, DIR_STRUCTURE)
    except VerifyPathException as e:
        logger.exception("Exception when verifying settings repository directory structure")
        raise e

    # 1. Get CNaaS-NMS default settings
    data_dir = Path(__file__).parent / "data"
    with open(os.path.join(data_dir, "default_settings.yml"), "r") as f_default_settings:
        settings: dict = yaml_safe_load(f_default_settings)

    settings_origin = {}
    for k in settings.keys():
        settings_origin[k] = "default"

    # 2. Get settings repo global settings
    get_type = "global"
    if device:
        # Some settings parsing require knowledge of group memberships
        groups = get_groups(device)
        settings, settings_origin = read_settings(
            local_repo_path,
            ["global", "base_system.yml"],
            "global->base_system.yml",
            settings,
            settings_origin,
            groups,
        )
    else:
        settings, settings_origin = read_settings(
            local_repo_path,
            ["global", "base_system.yml"],
            "global->base_system.yml",
            settings,
            settings_origin,
        )

    # 3. Get settings from special fabric classification (dist + core)
    if device_type and (device_type == DeviceType.DIST or device_type == DeviceType.CORE):
        settings, settings_origin = read_settings(
            local_repo_path,
            ["fabric", "base_system.yml"],
            "fabric->base_system.yml",
            settings,
            settings_origin,
        )

    # 4. Get settings repo device type settings
    if device_type:
        get_type = "devicetype {}".format(device_type.name)
        if device_type == DeviceType.UNKNOWN:
            if device is None:
                raise ValueError("It's not possible to get settings for devices with type UNKNOWN")
            else:
                logger.warning("Device type is UNKNOWN, trying to get settings for hostname {}".format(device.hostname))
        else:
            settings, settings_origin = read_settings(
                local_repo_path,
                [device_type.name.lower(), "base_system.yml"],
                "devicetype->base_system.yml",
                settings,
                settings_origin,
            )
    if device:
        get_type = "hostname {}".format(device.hostname)
        settings, settings_origin = read_settings(
            local_repo_path,
            ["global", "routing.yml"],
            "global->routing.yml",
            settings,
            settings_origin,
            groups,
        )
        settings, settings_origin = read_settings(
            local_repo_path,
            ["global", "vxlans.yml"],
            "global->vxlans.yml",
            settings,
            settings_origin,
            groups,
            device.hostname,
        )
        settings, settings_origin = read_settings(
            local_repo_path,
            ["global", "access_lists.yml"],
            "global->access_lists.yml",
            settings,
            settings_origin,
            groups,
        )
        settings = get_downstream_dependencies(device, settings)

        # 5. Get settings repo group specific settings
        primary_group = None
        # Check if the device is in the db
        try:
            device_state = inspect(device)
        except NoInspectionAvailable:
            device_state = None
        # Device is in the db
        if device_state is not None and device_state.persistent:
            primary_group = get_device_primary_groups().get(device.hostname)
        # Device is not in the db
        else:
            primary_group = get_primary_group_for_device(device)
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
                    "groups->{}->interfaces.yml".format(primary_group),
                    settings,
                    settings_origin,
                )
                settings, settings_origin = read_settings(
                    local_repo_path,
                    ["groups", primary_group, "routing.yml"],
                    "groups->{}->routing.yml".format(primary_group),
                    settings,
                    settings_origin,
                )

        # 6. Get settings repo device specific settings
        if os.path.isdir(os.path.join(local_repo_path, "devices", device.hostname)):
            settings, settings_origin = read_settings(
                local_repo_path,
                ["devices", device.hostname, "base_system.yml"],
                "device->{}->base_system.yml".format(device.hostname),
                settings,
                settings_origin,
            )
            settings, settings_origin = read_settings(
                local_repo_path,
                ["devices", device.hostname, "interfaces.yml"],
                "device->{}->interfaces.yml".format(device.hostname),
                settings,
                settings_origin,
            )
            settings, settings_origin = read_settings(
                local_repo_path,
                ["devices", device.hostname, "routing.yml"],
                "device->{}->routing.yml".format(device.hostname),
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
                [
                    device_type.name.lower(),
                    "interfaces_{}.yml".format(device_model.lower()),
                ],
                "{}->interfaces_{}.yml".format(device_type.name.lower(), model_name_sanitize(device_model)),
                settings,
                settings_origin,
            )

    else:
        # Some settings parsing require knowledge of group memberships
        groups = []
        settings, settings_origin = read_settings(
            local_repo_path,
            ["global", "routing.yml"],
            "global->routing.yml",
            settings,
            settings_origin,
            groups,
        )
        settings, settings_origin = read_settings(
            local_repo_path,
            ["global", "vxlans.yml"],
            "global->vxlans.yml",
            settings,
            settings_origin,
            groups,
        )
        settings, settings_origin = read_settings(
            local_repo_path,
            ["global", "access_lists.yml"],
            "global->access_lists.yml",
            settings,
            settings_origin,
            groups,
        )

    # Verify access_lists syntax
    # If access_lists and system_access_lists are keys in settings dict
    if "access_lists" in settings and "system_access_lists" in settings:
        check_system_access_lists(settings)

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
def get_group_settings() -> Tuple[f_groups, dict]:
    logger = get_logger()
    settings: dict = {}
    settings_origin: dict = {}

    local_repo_path = app_settings.SETTINGS_LOCAL
    try:
        verify_dir_structure(os.path.join(local_repo_path, "global"), DIR_STRUCTURE["global"])
    except VerifyPathException as e:
        logger.exception("Exception when verifying settings repository directory structure")
        raise e

    data_dir = Path(__file__).parent / "data"
    with open(os.path.join(data_dir, "default_groups.yml"), "r") as f_default_settings:
        default_settings: dict = yaml_safe_load(f_default_settings)

    settings, settings_origin = read_settings(
        local_repo_path, ["global", "groups.yml"], "global", settings, settings_origin
    )
    settings["groups"] += default_settings["groups"]
    check_settings_syntax(settings, settings_origin)
    return f_groups(**settings), settings_origin


@redis_lru_cache
def get_groups(device: Optional[Device] = None) -> List[str]:
    """Return list of names for valid groups."""
    groups: list[str] = []
    settings, origin = get_group_settings()
    if not settings or settings.groups is None:
        return groups
    for group in settings.groups:
        if device and not group.matches(device):
            continue
        groups.append(group.name)
    return groups


def get_group(group_name: str) -> Optional[f_group]:
    """Returns the group object if it's found."""
    settings, _ = get_group_settings()
    if not settings or settings.groups is None:
        return None
    return next((group for group in settings.groups if group.name == group_name), None)


def get_group_templates_branch(group_name: str) -> Optional[str]:
    """Returns a string containing the regex defining the specified
    group name if it's found."""
    return get_group_settings_asdict().get(group_name, {}).get("templates_branch")


@redis_lru_cache
def get_group_settings_asdict() -> Dict[str, Dict[str, Any]]:
    """Returns a dict with group name as key and other parameters as values"""
    settings, _ = get_group_settings()
    if not settings or not settings.groups:
        return {}
    group_dict: Dict[str, Dict[str, Any]] = {}
    for group in settings.groups:
        group_dict[group.name] = group.model_dump()
        del group_dict[group.name]["name"]
    return group_dict


def _resolve_jmespath_networks(network: dict, settings: dict, network_name: str) -> list[dict]:
    """Resolves and validates a JMESPath network reference into a list of address dictionaries."""
    addresses = jmespath.search(network["path"], settings)

    if not isinstance(addresses, list):
        raise AccessListGenerationError(
            f"Expected a list from jmespath search, got {type(addresses).__name__} in network definition {network_name}."
        )

    resolved_networks = []
    for address in addresses:
        try:
            interface = ip_interface(address)
        except ValueError:
            raise AccessListGenerationError(
                f"Expected an IP address or network from jmespath search, got {address} "
                f"(type {type(address).__name__}) in network definition {network_name}."
            )

        if network.get("strip_cidr"):
            formatted_address = str(interface.ip)
        else:
            formatted_address = str(interface.network)

        resolved_networks.append({"address": formatted_address})

    return resolved_networks


def _build_aerleon_definitions(settings: dict) -> naming.Naming:
    """
    Builds Aerleon Naming from settings network_definitions and service_definitions.
    Returns a naming.Naming object.
    """
    aerleon_definitions = naming.Naming()

    networks_dict = {}
    services_dict = {}
    for network_name, networks in settings.get("network_definitions", {}).items():
        network_list = []
        for network in networks:
            if "path" in network:
                resolved_addrs = _resolve_jmespath_networks(network, settings, network_name)
                network_list.extend(resolved_addrs)
            else:
                # Normal aerleon network definition
                network_list.append(network)

        networks_dict[network_name] = {"values": network_list}
    for service_name, services in settings.get("service_definitions", {}).items():
        services_dict[service_name] = services

    aerleon_definitions.ParseDefinitionsObject({"networks": networks_dict, "services": services_dict}, "")
    return aerleon_definitions


def napalm_to_aerleon(platform: str, device_model: Optional[str] = None) -> str:
    """
    Translates napalm platform to aerleon
    If not found it will return the platform as is
    """
    # There is no direct translation between napalm juniper and srx
    # So we manually handle it here
    if device_model and platform == "junos" and device_model.lower().startswith("srx"):
        return "srx"

    return AERLEON_LIB_MAPPER_REVERSE.get(NAPALM_LIB_MAPPER.get(platform, ""), platform)


def _get_aerleon_translated_terms(terms: TermsList, device_model: Optional[str] = None) -> TermsList:
    """
    Convert Napalm platform names (e.g. 'ios', 'eos') inside term dictionaries
    into their corresponding Aerleon generator names (e.g. 'cisco_ios',
    'arista_eos'). The translation is applied recursively to all nested dicts
    and lists.

    Returns a new list of translated term dictionaries.
    """

    def translate(value):
        if isinstance(value, str):
            return napalm_to_aerleon(value, device_model)
        if isinstance(value, dict):
            return {translate(k): translate(v) for k, v in value.items()}
        if isinstance(value, list):
            return [translate(item) for item in value]
        return value

    return [translate(term) for term in terms]


def _get_aerleon_inet(aerleon_platform: str, inet_family: Literal["ipv4", "ipv6"]) -> str:
    """
    Maps ipv4 or ipv6 to aerleon inet-format.
    Differs between different types of devices.
    More information here: https://aerleon.readthedocs.io/en/latest/reference/generators/

    To get support for other platforms define a custom header_map in f_access_list for that platform.
    """
    inet_family_map = {
        # Arista
        # napalm eos
        "arista": {"ipv4": "extended", "ipv6": "inet6"},
        # Cisco
        # napalm ios
        "cisco": {"ipv4": "extended", "ipv6": "inet6"},
        # napalm nxos
        "cisconx": {"ipv4": "extended", "ipv6": "inet6"},
        # napalm iosxr
        "ciscoxr": {"ipv4": "", "ipv6": "inet6"},
        # Juniper
        # napalm junos
        "juniper": {"ipv4": "inet", "ipv6": "inet6"},
        # juniper srx, no direct napalm -> aerleon translation
        "srx": {"ipv4": "inet", "ipv6": "inet6"},
    }
    return inet_family_map.get(aerleon_platform, {}).get(inet_family, inet_family)


def _get_all_access_lists(data: List[Dict[str, str]]) -> Iterator[str]:
    """
    Extracts all access lists from a vxlan or interface and returns them as a single list.

    Args:
        data: A vxlan or interface dictionary.

    Returns:
        An iterator of strings with all access list names.
    """
    for vi in data:
        for acl_setting in ["acl_ipv4_in", "acl_ipv4_out", "acl_ipv6_in", "acl_ipv6_out"]:
            if acl := vi.get(acl_setting):
                yield acl


def get_generated_access_lists(
    dev: Optional[Device] = None, platform: Optional[str] = None, settings: Optional[dict] = None
) -> Dict[str, str]:
    """
    Generate access lists for a given network device or platform.

    This function builds Aerleon policy definitions based on device settings and
    produces rendered access lists for the target platform. The platform may be
    provided explicitly or inferred from the device. Settings are loaded
    automatically if not supplied.

    Args:
        dev: Optional Device object used to derive platform and settings when not
            provided explicitly.
        platform: The platform name (e.g., "eos", "ios", "junos"). Overrides the
            device's platform if provided.
        settings: Optional settings dictionary. If omitted or empty, settings
            will be loaded automatically for the device.

    Returns:
        A dictionary mapping access list names to their generated configuration
        strings. IPv4 and IPv6 will be generated to the same output-string.
        Example: {ACL_NAME: "config_as_text"}

    Raises:
        AccessListGenerationError:
            - If the platform cannot be determined.
            - If Aerleon encounters an error during generation.
    """
    logger = get_logger()

    # Prefer platform argument, otherwise get from device.
    if platform is None:
        if dev is not None:
            platform = getattr(dev, "platform", None)

    if platform is None:
        raise AccessListGenerationError("Platform argument must be provided either directly or via a device")

    # When settings have not been passed in via arguments get_settings
    if not settings:
        settings, _ = get_settings(dev)

    # Fix for mypy to understand settings is not dict | None but only dict
    assert settings is not None

    device_model = dev.model if dev else None

    # Get aerleon platform name from NMS napalm platform
    aerleon_platform = napalm_to_aerleon(platform, device_model)
    # Could not get a valid aerleon platform
    if aerleon_platform not in AERLEON_LIB_MAPPER.keys():
        logger = get_logger()
        logger.error(
            f"Platform: {platform} (Aerleon platform: {aerleon_platform}) is not supported for access_list generation, no access-lists will be generated."
        )
        return {}

    # Set of all access_lists that should be generated for this device.
    # All devices will get global system_access_lists.
    generate_access_lists: Set[str] = set(settings.get("system_access_lists", []))

    # Add all acls found from vxlan to a dist-switch
    if dev and dev.device_type == DeviceType.DIST:
        generate_access_lists.update(_get_all_access_lists(settings.get("vxlans", {}).values()))
    # Add all interface-acls.
    if dev and dev.device_type in [DeviceType.ACCESS, DeviceType.CORE, DeviceType.DIST, DeviceType.FIREWALL]:
        generate_access_lists.update(_get_all_access_lists(settings.get("interfaces", [])))

    policies = []  # All access_lists that will be generated
    includes = {}  # A dict with acl_name: policy_dict if another access_list includes another acl.
    setting_acls: Dict[str, dict] = settings.get("access_lists", {})

    defs = _build_aerleon_definitions(settings)

    for access_list_name, access_list_dict in setting_acls.items():
        # Construct f_access_list object without validation
        access_list: f_access_list = f_access_list.model_construct(**access_list_dict)

        # Get aerleon header format, defaults to "{ACL_NAME} {INET_FAMILY}"
        # Try first to get the aerleon specific platform and fallback to napalm
        header = access_list.header_map.get(
            aerleon_platform, access_list.header_map.get(platform, "{ACL_NAME} {INET_FAMILY}")
        )

        inside_policies = []

        # Check if source/destination is empty and remove them with a debug log
        # As aerleon does not like terms with empty network definitions.
        filtered_acl_terms = []
        for acl_term in _get_aerleon_translated_terms(access_list.terms, device_model):
            # Include terms should always be included
            if acl_term.get("include"):
                filtered_acl_terms.append(acl_term)
                continue
            # When skip_terms_with_empty_network_definitions is False
            # Add all terms to filtered_acl_terms, even if they have empty network definitions.
            if not access_list.skip_terms_with_empty_network_definitions:
                filtered_acl_terms.append(acl_term)
                continue

            # Check if terms have empty network definitions and skip them with a debug log
            for field in ["source", "source-address", "destination", "destination-address"]:
                if networks := acl_term.get(field):
                    net_count = 0
                    if not isinstance(networks, list):
                        networks = [networks]
                    for network in networks:
                        try:
                            net_count += len(defs._GetNet(network))
                        except naming.UndefinedAddressError:
                            # Do nothing for this error, as aerleon will handle it later
                            pass
                    if net_count == 0:
                        logger.debug(
                            "Access list '{}' term '{}' has empty network definition for '{}': removing this term as skip_terms_with_empty_network_definitions is True".format(
                                access_list_name, acl_term.get("name"), field
                            )
                        )
                        break
            else:
                # If all above checks pass, add the term to filtered_acl_terms
                filtered_acl_terms.append(acl_term)

        # Add all access_lists to includes
        # Only needs to be done once as terms are inet-agnostic
        included_list: PolicyFilterTermsOnly = {"terms": filtered_acl_terms}
        includes.update({access_list_name: included_list})

        for inet_family in access_list.inet_families:
            # Format acl_header for the specific inet_family
            acl_header = header.format(
                ACL_NAME=access_list_name, INET_FAMILY=_get_aerleon_inet(aerleon_platform, inet_family)
            )
            inside_policy_dict: PolicyFilter = {
                "header": {"targets": {aerleon_platform: acl_header}, "comment": access_list.comment},
                "terms": filtered_acl_terms,
            }
            inside_policies.append(inside_policy_dict)

        # Only access list found in generate_access_lists should generate
        if access_list_name in generate_access_lists:
            policy_dict: PolicyDict = {
                "filename": access_list_name,
                "filters": inside_policies,
            }
            policies.append(policy_dict)

    try:
        # Generate all access-lists at once.
        generated_configs = _generate_acl(policies, defs, includes)
    except (ACLGenError, naming.Error) as e:
        error_msg = re.sub(r":\n<[^>]*>", ", ", str(e))
        raise AccessListGenerationError(error_msg)
    except PolicyTypeError as e:
        raise AccessListGenerationError(str(e))

    return generated_configs


@redis_lru_cache
def _generate_acl(
    policies: List[PolicyDict], defs: naming.Naming, includes: dict[str, PolicyFilterTermsOnly]
) -> dict[str, str]:
    # Aerleon uses absl as logging.
    # Override logging and set our own capture handler as the only log handler.
    absl_logging.use_python_logging(quiet=True)
    aerleon_logger = absl_logging.get_absl_logger()
    current_root_handlers = aerleon_logger.root.handlers
    for c_handler in current_root_handlers:
        aerleon_logger.root.removeHandler(c_handler)

    # Create the new handler and attach to aerleon_logger
    handler = CaptureHandler()
    handler.setLevel(logging.WARNING)
    aerleon_logger.addHandler(handler)

    try:
        configs = Generate(
            policies,
            defs,
            optimize=api_settings.ACCESS_LIST_OPTIMIZE,
            # Does not seem to work currently
            # investigate future use-cases
            shade_check=False,
            includes=includes,
        )
    finally:
        # Revert back absl handlers
        for c_handler in current_root_handlers:
            aerleon_logger.root.addHandler(c_handler)

        aerleon_logger.removeHandler(handler)

    if handler.records:
        logger = get_logger()
        for record in handler.records:
            # Remove not needed WARNING message
            record.msg = record.msg.lstrip("WARNING: ")
            # Use cnaas logger to emit aerleon logs
            logger.handle(record)

    if not configs:
        return {}
    # Remove suffix from filename
    return {re.sub(r"\.[^.]+$", "", k): v for k, v in configs.items()}


def get_groups_priorities(device: Optional[Device] = None, settings: Optional[f_groups] = None) -> Dict[str, int]:
    """Return dicts with {name: priority} for groups"""
    groups_priorities: dict[str, Any] = {}

    if not settings:
        settings, _ = get_group_settings()
    if not settings:
        return groups_priorities
    if settings.groups is None:
        return groups_priorities
    for group in settings.groups:
        if not group.group_priority or group.group_priority == 0:
            continue
        if device and not group.matches(device):
            continue
        groups_priorities[group.name] = group.group_priority

    return groups_priorities


def get_groups_priorities_sorted(
    device: Optional[Device] = None, settings: Optional[f_groups] = None
) -> Dict[str, int]:
    return {
        k: v
        for k, v in sorted(
            get_groups_priorities(device, settings).items(),
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
    with sqla_session() as session:  # type: ignore
        devices: List[Device] = session.query(Device).all()
        for dev in devices:
            groups = get_groups(dev)
            primary_group: str = find_primary_group(groups, groups_priorities_sorted)
            device_primary_group[dev.hostname] = primary_group
    return device_primary_group


def get_primary_group_for_device(dev: Device) -> str:
    """Matches device against groups. Does not require a session."""
    return find_primary_group(get_groups(dev), get_groups_priorities_sorted())


def update_device_primary_groups():
    device_primary_group = parse_device_primary_groups()
    if not device_primary_group:
        return
    with redis_session() as redis:  # type: ignore
        redis.hset("device_primary_group", mapping=device_primary_group)


def get_device_primary_groups(no_cache: bool = False) -> Dict[str, str]:
    """Returns a dict with {hostname: primary_group} from redis

    Args:
        no_cache: Update redis cache before returning data
    """
    logger = get_logger()
    # update redis if redis is empty
    with redis_session() as redis:  # type: ignore
        if not redis.exists("device_primary_group"):
            update_device_primary_groups()
    if no_cache:
        update_device_primary_groups()
    device_primary_group: dict = {}
    with redis_session() as redis:  # type: ignore
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
        AccessListGenerationError: There is an error when generating access_lists
    """
    logger = get_logger()
    logger.debug("Clearing redis-lru cache for settings")
    with redis_session() as redis_db:  # type: ignore
        mem_stats_before = redis_db.memory_stats()
        cache = NMSRedisLRU(redis_db)
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
    # Get all local platforms and try to generate global access_lists for that platform.
    platforms = []
    with sqla_session() as session:  # type: ignore
        device_platforms: List[Device] = (
            session.query(Device).distinct(Device.platform).where(Device.platform.is_not(None)).all()
        )
        platforms = [dev.platform for dev in device_platforms]
    for platform in platforms:
        get_generated_access_lists(platform=platform)
    test_devtypes = [DeviceType.ACCESS, DeviceType.DIST, DeviceType.CORE, DeviceType.FIREWALL]
    logger.debug("Rebuilding settings cache for devicetypes")
    for devtype in test_devtypes:
        settings, _ = get_settings(device_type=devtype)
        for platform in platforms:
            # Generate access_lists for all dev_types and platforms
            get_generated_access_lists(platform=platform, settings=settings)
    logger.debug("Rebuilding settings cache for device specific settings")
    with sqla_session() as session:  # type: ignore
        for hostname in os.listdir(os.path.join(app_settings.SETTINGS_LOCAL, "devices")):
            hostname_path = os.path.join(app_settings.SETTINGS_LOCAL, "devices", hostname)
            if not os.path.isdir(hostname_path) or hostname.startswith("."):
                continue
            if not Device.valid_hostname(hostname):
                continue
            dev: Optional[Device] = session.query(Device).filter(Device.hostname == hostname).one_or_none()
            if dev is None or dev.device_type == DeviceType.UNKNOWN:
                logger.warning(f"Device {hostname} specified in settings/devices but it was not found in database")
                continue
            get_settings(dev, dev.device_type)
            # Try to generate access_lists for a specific device
            if dev.platform:
                get_generated_access_lists(dev)
    logger.debug("Rebuilding settings cache for device models")
    for devtype_str, device_models in get_model_specific_configfiles(True).items():
        devtype = DeviceType[devtype_str]
        for device_model in device_models:
            get_settings(None, devtype, device_model)
    logger.debug("Rechecking settings collisions")
    check_settings_collisions(api_settings.GLOBAL_UNIQUE_VLANS)
