import yaml


def get_apidata(config='/etc/cnaas-nms/api.yml'):
    with open(config, 'r') as api_file:
        return yaml.safe_load(api_file)
