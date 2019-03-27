import os
from typing import List

import yaml

from cnaas_nms.db.settings_fields import f_root


DIR_STRUCTURE = {
    'global':
        {
            'base_system.yml': 'file'
        },
    'core': {},
    'dist': {},
    'access': {},
    'fabric': {}
}


def verify_dir_structure(path: str, dir_structure: dict):
    for item, subitem in dir_structure.items():
        if isinstance(subitem, str) and subitem == 'file':
            filename = os.path.join(path, item)
            if not os.path.isfile(filename):
                if os.path.exists(filename):
                    raise ValueError(f"{filename} is not a regular file")
                else:
                    raise ValueError(f"File {filename} not found")
        else:
            dirname = os.path.join(path, item)
            if not os.path.isdir(dirname):
                if os.path.exists(dirname):
                    raise ValueError(f"{dirname} is not a directory")
                else:
                    raise ValueError(f"Directory {dirname} not found")

            if subitem:
                verify_dir_structure(os.path.join(path, item), dir_structure[item])


def keys_exists(element, keys):
    _element = element
    for key in keys:
        try:
            _element = _element[key]
        except KeyError:
            return False
    return True


def get_setting_filename(repo_root: str, path: List[str]):
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


def get_settings():
    with open('/etc/cnaas-nms/repository.yml', 'r') as db_file:
        repo_config = yaml.safe_load(db_file)

    local_repo_path = repo_config['settings_local']
    try:
        verify_dir_structure(local_repo_path, DIR_STRUCTURE)
    except:
        raise

    with open(get_setting_filename(local_repo_path, ['global', 'base_system.yml']), 'r') as g_base_sys_f:
        global_dict = yaml.safe_load(g_base_sys_f)
        print(f_root(**global_dict))




