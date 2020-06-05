#!/bin/env python3

import sys
import os
import requests
import jinja2
import yaml


api_url = os.environ['CNAASURL']
headers = {"Authorization": "Bearer "+os.environ['JWT_AUTH_TOKEN']}


def get_entrypoint(platform, device_type):
    mapfile = os.path.join(platform, 'mapping.yml')
    if not os.path.isfile(mapfile):
        raise Exception("File {} not found".format(mapfile))
    with open(mapfile, 'r') as f:
        mapping = yaml.safe_load(f)
        template_file = mapping[device_type]['entrypoint']
    return template_file


def get_device_details(hostname):
    r = requests.get(
        f"{api_url}/api/v1.0/device/{hostname}",
        headers=headers)
    if r.status_code != 200:
        raise Exception("Could not query device API")
    device_data = r.json()['data']['devices'][0]

    r = requests.get(
        f"{api_url}/api/v1.0/device/{hostname}/generate_config",
        headers=headers)
    if r.status_code != 200:
        raise Exception("Could not query generate_config API")
    config_data = r.json()['data']['config']

    return device_data['device_type'], device_data['platform'], \
        config_data['available_variables'], config_data['generated_config']


def render_template(platform, device_type, variables):
    jinjaenv = jinja2.Environment(
        loader=jinja2.FileSystemLoader(platform),
        undefined=jinja2.StrictUndefined, trim_blocks=True
    )
    template_secrets = {}
    for env in os.environ:
        if env.startswith('TEMPLATE_SECRET_'):
            template_secrets[env] = os.environ[env]
    template_vars = {**variables, **template_secrets}
    template = jinjaenv.get_template(get_entrypoint(platform, device_type))
    return template.render(**template_vars)


def schedule_apply_dryrun(hostname, config):
    data = {
        'full_config': config,
        'dry_run': True
    }
    r = requests.post(
        f"{api_url}/api/v1.0/device/{hostname}/apply_config",
        headers=headers,
        json=data
    )
    if r.status_code != 200:
        raise Exception("Could not schedule apply_config job via API")
    return r.json()['job_id']


def main():
    if len(sys.argv) != 2:
        print("Usage: template_dry_run.py <hostname>")
        sys.exit(1)

    hostname = sys.argv[1]
    try:
        device_type, platform, variables, old_config = get_device_details(hostname)
    except Exception as e:
        print(e)
        sys.exit(2)
    variables['host'] = hostname
    new_config = render_template(platform, device_type, variables)
    print("OLD TEMPLATE CONFIG ==============================")
    print(old_config)
    print("NEW TEMPLATE CONFIG ==============================")
    print(new_config)

    try:
        input("Start apply_config dry run? Ctrl-c to abort...")
    except KeyboardInterrupt:
        print("Exiting...")
    else:
        print("Apply config dry_run job: {}".format(schedule_apply_dryrun(hostname, new_config)))


if __name__ == "__main__":
    main()
