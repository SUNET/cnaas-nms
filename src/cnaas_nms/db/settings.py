import os
import pkg_resources
from typing import List, Optional

import yaml
from pydantic.error_wrappers import ValidationError

from cnaas_nms.db.settings_fields import f_root
from cnaas_nms.tools.mergedict import MetadataDict, merge_dict_origin
from cnaas_nms.tools.log import get_logger

logger = get_logger()


class VerifyPathException(Exception):
    pass


class SettingsSyntaxError(Exception):
    pass


DIR_STRUCTURE = {
    'global':
        {
            'base_system.yml': 'file'
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
    if not keys_exists(DIR_STRUCTURE, path):
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
        for error in e.errors():
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


def get_settings(hostname: Optional[str] = None):
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
        default_settings: dict = yaml.safe_load(f_default_settings)

    # 2. Get settings repo global settings
    with open(get_setting_filename(local_repo_path, ['global', 'base_system.yml']), 'r')\
            as f_g_base_sys:
        global_settings: dict = yaml.safe_load(f_g_base_sys)

        (merged_settings, merged_settings_metadata) = \
            merge_dict_origin(default_settings, global_settings, 'default', 'global')

    # 3. Get settings repo device type settings

    # 4. Get settings repo device specific settings

    # 5. Verify syntax
    check_settings_syntax(merged_settings, merged_settings_metadata)
    print(f_root(**merged_settings).dict())
    print(merged_settings_metadata)
    return f_root(**merged_settings).dict()

