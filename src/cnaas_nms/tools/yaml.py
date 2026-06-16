import yaml

if yaml.__with_libyaml__:  # type: ignore[attr-defined]
    SafeLoader = yaml.CSafeLoader  # type: ignore[attr-defined]
else:
    SafeLoader = yaml.SafeLoader


def yaml_safe_load(stream):
    return yaml.load(stream, Loader=SafeLoader)  # type: ignore[attr-defined]
