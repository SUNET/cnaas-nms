import os
import re
import pkg_resources
from typing import List, Optional, Union, Tuple, Set

import yaml
from pydantic.error_wrappers import ValidationError

from cnaas_nms.db.settings_fields import f_root, f_groups
from cnaas_nms.tools.mergedict import MetadataDict, merge_dict_origin
from cnaas_nms.db.device import Device, DeviceType, DeviceState
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.mgmtdomain import Mgmtdomain
from cnaas_nms.tools.log import get_logger

logger = get_logger()


class VerifyPathException(Exception):
    pass


class SettingsSyntaxError(Exception):
    pass


class VlanConflictError(Exception):
    pass


DIR_STRUCTURE_HOST = {
    'base_system.yml': 'file',
    'interfaces.yml': 'file'
}

DIR_STRUCTURE = {
    'global':
    {
        'base_system.yml': 'file',
        'groups.yml': 'file',
        'routing.yml': 'file',
        'vxlans.yml': 'file'
    },
    'fabric':
    {
        'base_system.yml': 'file'
    },
    'core':
    {
        'base_system.yml': 'file'
    },
    'dist':
    {
        'base_system.yml': 'file'
    },
    'access':
    {
        'base_system.yml': 'file'
    },
    'devices':
    {
        Device: DIR_STRUCTURE_HOST
    }
}


def verify_dir_structure(path: str, dir_structure: dict):
    """Verify that given path complies to given directory structure.
    Raises:
        VerifyPathException
    """
    for item, subitem in dir_structure.items():
        if isinstance(subitem, str) and subitem == 'file':
            filename = os.path.join(path, item)
            if not os.path.isfile(filename):
                if os.path.exists(filename):
                    raise VerifyPathException(f"{filename} is not a regular file")
                else:
                    raise VerifyPathException(f"File {filename} not found")
        elif item is Device:
            for hostname in os.listdir(path):
                hostname_path = os.path.join(path, hostname)
                if not os.path.isdir(hostname_path) or hostname.startswith('.'):
                    continue
                if not Device.valid_hostname(hostname):
                    continue
                verify_dir_structure(hostname_path, subitem)
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
    if path[0] == 'devices':
        if not len(path) >= 3:
            raise ValueError("Invalid directory structure for devices settings")
        if not keys_exists(DIR_STRUCTURE_HOST, path[2:]):
            raise ValueError("File not defined in DIR_STRUCTURE")
    elif not keys_exists(DIR_STRUCTURE, path):
        raise ValueError("File not defined in DIR_STRUCTURE")
    return os.path.join(repo_root, *path)


def get_pydantic_error_value(data: dict, loc: tuple):
    """Get the actual value that caused the error in pydantic"""
    try:
        obj = data
        for item in loc:
            obj = obj[item]
    except KeyError:
        return None
    else:
        return obj


def check_settings_syntax(settings_dict: dict, settings_metadata_dict: dict):
    """Verify settings syntax and return a somewhat helpful error message.

    Raises:
        SettingsSyntaxError
    """
    try:
        f_root(**settings_dict)
    except ValidationError as e:
        msg = ''
        for num, error in enumerate(e.errors()):
            # If there are two errors and the last one is of type none allowed
            # then skip recording the second error because it's an implication
            # of the first error (the value has to be correct or none)
            # TODO: handle multiple occurrences of this?
            if len(e.errors()) == 2 and num == 1 and error['type'] == 'type_error.none.allowed':
                continue
            # TODO: Find a way to present customised error message when string
            # regex match fails instead of just showing the regex pattern.
            loc = error['loc']
            error_msg = "Validation error for setting {}, bad value: {} (value origin: {})\n".format(
                '->'.join(str(x) for x in loc),
                get_pydantic_error_value(settings_dict, loc),
                settings_metadata_dict[loc[0]]
            )
            error_msg += "Message: {}\n".format(error['msg'])
            msg += error_msg
        logger.error(msg)
        raise SettingsSyntaxError(msg)


def check_settings_collisions(settings_dict, unique_vlans=True):
    """Check settings for any duplicates/collisions.
    This will call get_settings on all devices so make sure to not call this
    from get_settings.

    Args:
        settings_dict:
        unique_vlans: If enabled VLANs has to be globally unique

    Returns:

    """
    mgmt_vlans: Set[int] = set()
    global_vlans: Set[int] = set()
    device_vlan_ids: dict[str, Set[int]] = {}  # save used VLAN ids per device
    device_vlan_names: dict[str, Set[str]] = {}  # save used VLAN names per device
    with sqla_session() as session:
        mgmtdoms = session.query(Mgmtdomain).all()
        for mgmtdom in mgmtdoms:
            if mgmtdom.vlan and isinstance(mgmtdom.vlan, int):
                if unique_vlans and mgmtdom.vlan in mgmt_vlans:
                    raise VlanConflictError(
                        "Management VLAN {} used in multiple management domains".format(
                            mgmtdom.vlan
                        ))
                mgmt_vlans.add(mgmtdom.vlan)
        global_vlans = mgmt_vlans
        managed_devices: List[Device] = \
            session.query(Device).filter(Device.state == DeviceState.MANAGED).all()
        for dev in managed_devices:
            dev_settings, _ = get_settings(dev.hostname, dev.device_type)
            print(dev_settings)
            if 'vxlans' not in dev_settings:
                continue
            for vxlan in dev_settings['vxlans']:
                print("DEBUG10: {} {}".format(dev.hostname, vxlan))
                # VLAN id checks
                if 'vlan_id' not in vxlan or not isinstance(vxlan['vlan_id'], int):
                    continue
                if unique_vlans and vxlan['vlan_id'] in global_vlans:
                    raise VlanConflictError(
                        "VLAN id {} used in VXLAN {} is already used elsewhere".format(
                            vxlan['vlan_id'], vxlan['name']
                        ))
                elif dev.hostname in device_vlan_ids and \
                        vxlan['vlan_id'] in device_vlan_ids[dev.hostname]:
                    raise VlanConflictError("VLAN id {} used multiple times in device {}".format(
                        vxlan['vlan_id'], dev.hostname
                    ))
                else:
                    device_vlan_ids[dev.hostname] = {vxlan['vlan_id']}
                    global_vlans.add(vxlan['vlan_id'])
                # VLAN name checks
                if 'vlan_name' not in vxlan or not isinstance(vxlan['vlan_name'], str):
                    continue
                if dev.hostname in device_vlan_names and \
                        vxlan['vlan_name'] in device_vlan_names[dev.hostname]:
                    raise VlanConflictError("VLAN name {} used multiple times in device {}".format(
                        vxlan['vlan_name'], dev.hostname
                    ))
                else:
                    device_vlan_names[dev.hostname] = {vxlan['vlan_name']}
    print("DEBUG00 {}".format(mgmt_vlans))
    print("DEBUG01 {}".format(global_vlans))
    print("DEBUG02 {}".format(device_vlan_ids))
    print("DEBUG03 {}".format(device_vlan_names))


def read_settings(local_repo_path: str, path: List[str], origin: str,
                  merged_settings, merged_settings_origin,
                  groups: List[str] = None, hostname: str = None) -> Tuple[dict, dict]:
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
    with open(get_setting_filename(local_repo_path, path), 'r') as f:
        settings: Union[List, dict] = yaml.safe_load(f)
        if groups or hostname:
            syntax_dict, syntax_dict_origin = merge_dict_origin({}, settings, {}, origin)
            check_settings_syntax(syntax_dict, syntax_dict_origin)
            settings = filter_yamldata(settings, groups, hostname)
        if settings and isinstance(settings, dict):
            return merge_dict_origin(merged_settings, settings, merged_settings_origin, origin)
        else:
            return merged_settings, merged_settings_origin


def filter_yamldata(data: Union[List, dict], groups: List[str], hostname: str, recdepth=100) -> \
        Union[List, dict]:
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
            f_item = filter_yamldata(item, groups, hostname, recdepth-1)
            if f_item:
                ret_l.append(f_item)
        return ret_l
    elif isinstance(data, dict):
        ret_d = {}
        for k, v in data.items():
            do_filter = False
            group_match = False
            hostname_match = False
            if k == 'groups':
                if not v:
                    continue
                if not isinstance(v, list):  # Should already be checked by pydantic now
                    raise SettingsSyntaxError(
                        "Groups field must be a list or empty (currently {}) in: {}".
                        format(type(v).__name__, data))
                do_filter = True
                for group in v:
                    if group in groups:
                        group_match = True
                        ret_d[k] = v
            elif k == 'devices':
                if not v:
                    continue
                if not isinstance(v, list):  # Should already be checked by pydantic now
                    raise SettingsSyntaxError(
                        "Devices field must be a list or empty (currently {}) in: {}".
                        format(type(v).__name__, data))
                do_filter = True
                if hostname in v:
                    hostname_match = True
                    ret_d[k] = v
            if do_filter and not (group_match or hostname_match):
                return {}
            else:
                ret_d[k] = filter_yamldata(v, groups, hostname, recdepth-1)
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
            for vxlan in ds_settings['vxlans']:
                if vxlan['name'] not in [d['name'] for d in settings['vxlans']]:
                    settings['vxlans'].append(vxlan)
    return settings


def get_settings(hostname: Optional[str] = None, device_type: Optional[DeviceType] = None) -> \
        Tuple[dict, dict]:
    """Get settings to use for device matching hostname or global
    settings if no hostname is specified."""
    with open('/etc/cnaas-nms/repository.yml', 'r') as repo_file:
        repo_config = yaml.safe_load(repo_file)

    local_repo_path = repo_config['settings_local']
    try:
        verify_dir_structure(local_repo_path, DIR_STRUCTURE)
    except VerifyPathException as e:
        logger.exception("Exception when verifying settings repository directory structure")
        raise e

    # 1. Get CNaaS-NMS default settings
    data_dir = pkg_resources.resource_filename(__name__, 'data')
    with open(os.path.join(data_dir, 'default_settings.yml'), 'r') as f_default_settings:
        settings: dict = yaml.safe_load(f_default_settings)

    settings_origin = {}
    for k in settings.keys():
        settings_origin[k] = 'default'

    # 2. Get settings repo global settings
    settings, settings_origin = read_settings(
        local_repo_path, ['global', 'base_system.yml'], 'global', settings, settings_origin)
    # 3. Get settings from special fabric classification (dist + core)
    if device_type and (device_type == DeviceType.DIST or device_type == DeviceType.CORE):
        settings, settings_origin = read_settings(
            local_repo_path, ['fabric', 'base_system.yml'], 'fabric',
            settings, settings_origin)
    # 4. Get settings repo device type settings
    if device_type:
        settings, settings_origin = read_settings(
            local_repo_path, [device_type.name.lower(), 'base_system.yml'], 'devicetype',
            settings, settings_origin)
    # 5. Get settings repo device specific settings
    if hostname:
        if os.path.isdir(os.path.join(local_repo_path, 'devices', hostname)):
            settings, settings_origin = read_settings(
                local_repo_path, ['devices', hostname, 'base_system.yml'], 'device',
                settings, settings_origin)
            settings, settings_origin = read_settings(
                local_repo_path, ['devices', hostname, 'interfaces.yml'], 'device',
                settings, settings_origin)
        # Some settings parsing require knowledge of group memberships
        groups = get_groups(hostname)
        settings, settings_origin = read_settings(
            local_repo_path, ['global', 'routing.yml'], 'global',
            settings, settings_origin, groups)
        settings, settings_origin = read_settings(
            local_repo_path, ['global', 'vxlans.yml'], 'global',
            settings, settings_origin, groups, hostname)
        settings = get_downstream_dependencies(hostname, settings)
    # Verify syntax
    check_settings_syntax(settings, settings_origin)
    return f_root(**settings).dict(), settings_origin


def get_group_settings(hostname: Optional[str] = None,
                       device_type: Optional[DeviceType] = None):
    settings: dict = {}
    settings_origin: dict = {}

    with open('/etc/cnaas-nms/repository.yml', 'r') as repo_file:
        repo_config = yaml.safe_load(repo_file)
    local_repo_path = repo_config['settings_local']
    try:
        verify_dir_structure(local_repo_path, DIR_STRUCTURE)
    except VerifyPathException as e:
        logger.exception("Exception when verifying settings repository directory structure")
        raise e
    settings, settings_origin = read_settings(local_repo_path,
                                              ['global', 'groups.yml'],
                                              'global',
                                              settings,
                                              settings_origin)
    check_settings_syntax(settings, settings_origin)
    return f_groups(**settings).dict(), settings_origin


def get_groups(hostname=''):
    groups = []
    if hostname is not '':
        settings, origin = get_group_settings(hostname=hostname)
    else:
        settings, origin = get_group_settings()
    if settings is None:
        return groups
    if 'groups' not in settings:
        return groups
    if settings['groups'] is None:
        return groups
    for group in settings['groups']:
        if 'name' not in group['group']:
            continue
        if 'regex' not in group['group']:
            continue
        if hostname and not re.match(group['group']['regex'], hostname):
            continue
        groups.append(group['group']['name'])
    return groups
