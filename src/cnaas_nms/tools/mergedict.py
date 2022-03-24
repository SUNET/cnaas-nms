from collections import namedtuple

MetadataDict = namedtuple("MetadataDict", ["data", "metadata"])


def merge_dict_origin(base: dict, override: dict, prev: dict, override_name: str) -> MetadataDict:
    """Merge two dictionaries and save info on what value originated  from which dict, saving values already set by previous run."""
    data = {}
    metadata = {}
    for base_key, base_value in base.items():
        if base_key in override:
            data[base_key] = override[base_key]
            metadata[base_key] = override_name
        else:
            data[base_key] = base_value
            metadata[base_key] = prev[base_key]
    for override_key, override_value in override.items():
        if override_key not in data:
            data[override_key] = override_value
            metadata[override_key] = override_name
    return MetadataDict(data, metadata)
