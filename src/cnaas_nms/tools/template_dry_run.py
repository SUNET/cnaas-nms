#!/bin/env python3

import sys
import os
import argparse

from jinja_helpers import get_environment_secrets

try:
    import requests
    import jinja2
    import yaml
except ModuleNotFoundError as e:
    print("Please install python modules requests, jinja2 and yaml: {}".format(e))
    sys.exit(3)

if 'CNAASURL' not in os.environ or 'JWT_AUTH_TOKEN' not in os.environ:
    print("Please export environment variables CNAASURL and JWT_AUTH_TOKEN")
    sys.exit(4)

api_url = os.environ['CNAASURL']
headers = {"Authorization": "Bearer "+os.environ['JWT_AUTH_TOKEN']}
verify_tls = True

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
        verify=verify_tls,
        headers=headers)
    if r.status_code != 200:
        raise Exception("Could not query device API")
    device_data = r.json()['data']['devices'][0]

    r = requests.get(
        f"{api_url}/api/v1.0/device/{hostname}/generate_config",
        verify=verify_tls,
        headers=headers)
    if r.status_code != 200:
        raise Exception("Could not query generate_config API")
    config_data = r.json()['data']['config']

    return device_data['device_type'], device_data['platform'], \
        config_data['available_variables'], config_data['generated_config']


def load_jinja_filters():
    try:
        import jinja_filters
        return jinja_filters.FILTERS
    except ModuleNotFoundError as error:
        print(
            f'jinja_filters.py could not be loaded from PYTHONPATH, proceeding without filters: '
            '{error}'
        )
        return {}


def render_template(platform, device_type, variables):
    # Jinja env should match nornir_helper.cnaas_ninja_env
    jinjaenv = jinja2.Environment(
        loader=jinja2.FileSystemLoader(platform),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True
    )
    jfilters = load_jinja_filters()
    jinjaenv.filters.update(jfilters)
    print("Jinja filters added: {}".format([*jfilters]))
    template_vars = {**variables, **get_environment_secrets()}
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
        verify=verify_tls,
        json=data
    )
    if r.status_code != 200:
        raise Exception("Could not schedule apply_config job via API")
    return r.json()['job_id']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("hostname")
    parser.add_argument("-k", "--skip-verify", help="skip TLS cert verification", action="store_true")
    args = parser.parse_args()

    hostname = args.hostname
    if args.skip_verify:
        global verify_tls
        verify_tls = False
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
        input("Start apply_config dry run? Ctrl-C to abort or enter to continue...")
    except KeyboardInterrupt:
        print("Exiting...")
    else:
        print("Apply config dry_run job: {}".format(schedule_apply_dryrun(hostname, new_config)))


if __name__ == "__main__":
    main()
