#!/bin/env python3

import argparse
import os
import sys

from jinja_helpers import get_environment_secrets

try:
    import jinja2
    import requests
    import yaml
    from jinja2.meta import find_undeclared_variables
except ModuleNotFoundError as e:
    print("Please install python modules requests, jinja2 and (ruamel.)yaml: {}".format(e))
    print("Optionally install netutils for more filters")
    sys.exit(3)

if "CNAASURL" not in os.environ or "JWT_AUTH_TOKEN" not in os.environ:
    print("Please export environment variables CNAASURL and JWT_AUTH_TOKEN")
    sys.exit(4)

api_url = os.environ["CNAASURL"]
headers = {"Authorization": "Bearer " + os.environ["JWT_AUTH_TOKEN"]}
verify_tls = True


def get_entrypoint(platform, device_type):
    mapfile = os.path.join(platform, "mapping.yml")
    if not os.path.isfile(mapfile):
        raise Exception("File {} not found".format(mapfile))
    with open(mapfile, "r") as f:
        mapping = yaml.safe_load(f)
        template_file = mapping[device_type]["entrypoint"]
    return template_file


def get_device_details(hostname):
    r = requests.get(f"{api_url}/api/v1.0/device/{hostname}", verify=verify_tls, headers=headers)
    if r.status_code != 200:
        raise Exception("Could not query device API")
    device_data = r.json()["data"]["devices"][0]

    r = requests.get(f"{api_url}/api/v1.0/device/{hostname}/generate_config", verify=verify_tls, headers=headers)
    if r.status_code != 200:
        raise Exception("Could not query generate_config API")
    config_data = r.json()["data"]["config"]

    return (
        device_data["device_type"],
        device_data["platform"],
        config_data["available_variables"],
        config_data["generated_config"],
    )


def load_jinja_filters():
    ret = {}
    try:
        import jinja_filters

        ret = jinja_filters.FILTERS
    except ModuleNotFoundError as e:
        print("jinja_filters.py could not be loaded from PYTHONPATH, proceeding without filters: " f"{e}")
    try:
        from netutils.utils import jinja2_convenience_function

        ret = {**ret, **jinja2_convenience_function()}
    except ModuleNotFoundError as e:
        print("netutils could not be loaded from PYTHONPATH, proceeding without filters: " f"{e}")
    return ret


def render_template(platform, device_type, variables):
    # Jinja env should match nornir_helper.cnaas_ninja_env
    jinjaenv = jinja2.Environment(
        loader=jinja2.FileSystemLoader(platform),
        undefined=jinja2.DebugUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    jfilters = load_jinja_filters()
    jinjaenv.filters.update(jfilters)
    template_vars = {**variables, **get_environment_secrets()}
    template = jinjaenv.get_template(get_entrypoint(platform, device_type))
    rendered = template.render(**template_vars)
    # Find undefined variables, if
    ast = jinjaenv.parse(rendered)
    undefined_vars = find_undeclared_variables(ast=ast)
    if undefined_vars:
        for var in undefined_vars:
            if var.startswith("TEMPLATE_SECRET_"):
                template_vars[var] = "dummyvalue"
                print('Undefined secret variable, set to "dummyvalue": {}'.format(var))
            else:
                print("Undefined variable: {}".format(var))
        rendered = template.render(**template_vars)
    return rendered


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("hostname")
    parser.add_argument("interface")
    parser.add_argument("-k", "--skip-verify", help="skip TLS cert verification", action="store_true")
    parser.add_argument(
        "-s", "--search-lines", help="how many lines to search after interface name (default 20)", type=int
    )
    parser.add_argument("-p", "--print-lines", help="how many lines to print after match (default 5)", type=int)
    parser.add_argument("-m", "--match", help="""text to match for after interface (default "evpn")""")
    args = parser.parse_args()

    hostname = args.hostname
    interface = args.interface
    if args.skip_verify:
        global verify_tls
        verify_tls = False
    try:
        device_type, platform, variables, old_config = get_device_details(hostname)
    except Exception as e:
        print(e)
        sys.exit(2)
    if args.search_lines:
        search_lines = args.search_lines
    else:
        search_lines = 20
    if args.print_lines:
        print_lines = args.print_lines
    else:
        print_lines = 5
    if args.match:
        match_str = args.match
    else:
        match_str = "evpn"
    variables["host"] = hostname
    new_variables = variables
    new_interface = {}
    for intf in variables["interfaces"]:
        if intf["name"] == interface:
            new_interface = {
                "name": interface,
                "ifclass": "downlink",
                "redundant_link": True,
                "indexnum": intf["indexnum"],
                "data": {},
            }
    new_variables["interfaces"] = [new_interface]
    new_config = render_template(platform, device_type, variables)
    save_after = 0
    saved_lines = []
    for line in new_config.splitlines():
        if save_after > 0:
            saved_lines.append(line)
            save_after -= 1
        if interface in line:
            saved_lines.append(line)
            save_after = search_lines

    print_after = 0
    for line in saved_lines:
        if print_after > 0:
            print(line)
            print_after -= 1
        if match_str in line:
            print(line)
            print_after = print_lines


if __name__ == "__main__":
    main()
