import copy
from collections import namedtuple

from cnaas_nms.app_settings import api_settings

MetadataDict = namedtuple("MetadataDict", ["data", "metadata"])


def merge_dict_origin(base: dict, override: dict, prev: dict, override_name: str) -> MetadataDict:
    """Merge two dictionaries and save info on what value originated
    from which dict, saving values already set by previous run."""
    settings_to_merge = api_settings.SETTINGS_KEYS_TO_MERGE or []

    data = copy.deepcopy(base)
    metadata = {}

    for base_key, base_value in data.items():
        metadata[base_key] = prev[base_key]

        if base_key in override and base_key not in settings_to_merge:
            data[base_key] = override[base_key]
            metadata[base_key] = override_name
        elif base_key in override and base_key in settings_to_merge:
            if isinstance(data[base_key], dict):
                data[base_key].update(override[base_key])
            elif isinstance(data[base_key], list):
                data[base_key] += override[base_key]
            metadata[base_key] = prev[base_key] + ", " + override_name

    # Only consider keys not in base dict, therefore no merging required in this loop
    for override_key, override_value in override.items():
        if override_key not in data:
            data[override_key] = override_value
            metadata[override_key] = override_name

    return MetadataDict(data, metadata)
