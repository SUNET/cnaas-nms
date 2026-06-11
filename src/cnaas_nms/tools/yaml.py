import yaml

if yaml.__with_libyaml__:
    SafeLoader = yaml.CSafeLoader
else:
    SafeLoader = yaml.SafeLoader


def yaml_safe_load(stream):
    return yaml.load(stream, Loader=SafeLoader)
