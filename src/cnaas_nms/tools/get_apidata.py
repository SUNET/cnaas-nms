import yaml


def get_apidata(config='/etc/cnaas-nms/api.yml') -> dict:
    defaults = {
        'allow_apply_config_liverun': False
    }
    with open(config, 'r') as api_file:
        return {**defaults, **yaml.safe_load(api_file)}
