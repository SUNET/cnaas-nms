from typing import List

# TODO: move all group related things here from settings
#  make new settings_helper.py with (verify_dir_structure etc) and separate settings_groups for get_settigns groups?
#  use get_group_settings_asdict instead of passing dict in get_groups_using_branch below


def get_groups_using_branch(branch_name: str, group_settings: dict) -> List[str]:
    """Returns a list of group names that use the specified branch name"""
    groups = []
    for group_name, group_data in group_settings.items():
        if group_data.get("templates_branch") == branch_name:
            groups.append(group_name)
    return groups
