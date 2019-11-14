#!/usr/bin/env python3
import textwrap
import requests
import yaml


class InitFabric(object):
    def __init__(self):
        self.devices = []
        self.session = requests.Session()
        print(textwrap.dedent("""
            This script will initialize the CNaaS-NMS database with the first set of
            devices to get the fabric up and running.
            Only run this script for the initial deployment of a new fabric.
            """))
        self.url = input("CNaaS URL (https://lab.sunet.se:8443): ")
        validate_cert_str = input("Validate server cert [Y/n]: ")
        if validate_cert_str == 'n':
            self.session.verify = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.jwt_token = input("JWT token: ")
        self.session.headers.update(self.auth_header())
        self.platform = input("Device platform/OS (eos,junos,nx-os etc): ")
        self.mgmt_lo_net = input("Management loopback range (10.100.3.0/24): ")
        evpn_spines = input("Enter devices that will act as core/spine, or all devices if no core"
                            "(use space as separator, ex: cn-dist-1 cn-dist-2): ")
        self.evpn_spines = evpn_spines.split()

    def auth_header(self):
        return {
            "Authorization": f"Bearer {self.jwt_token}",
            "Content-Type": "application/json"
        }

    def pre_check(self):
        r = self.session.get(f"{self.url}/api/v1.0/devices")
        if not r.status_code == 200:
            raise Exception("Bad response from API, is the URL and auth token correct? (code {})".
                            format(r.status_code))
        dev_list = []
        for dev in r.json()['data']['devices']:
            dev_list.append(dev['hostname'])
        if not dev_list:
            return
        print("Found existing devices in database: {}".format(", ".join(dev_list)))
        ask_delete = input("Do you want to delete existing devices? [y/N]: ")
        if ask_delete == 'y':
            r_m = self.session.get(f"{self.url}/api/v1.0/mgmtdomains")
            for dom in r_m.json()['data']['mgmtdomains']:
                domid = dom['id']
                self.session.delete(f"{self.url}/api/v1.0/mgmtdomain/{domid}")
            for dev in r.json()['data']['devices']:
                print("Deleting {} from database".format(dev['hostname']))
                devid = dev['id']
                self.session.delete(f"{self.url}/api/v1.0/device/{devid}")

    def add_devices(self):
        devices = []
        while True:
            add_dist = input("Add one (more) pair of dist devices? [y/N]: ")
            if add_dist == "y":
                new_devices = self.add_distpair()
                devices += new_devices
            else:
                break
        self.add_uplinks(devices)
        self.devices = devices

    def add_distpair(self):
        print("-"*80)
        print("Adding new distribution switch pair:")
        dev1_hostname = input("Device one hostname: ")
        dev2_hostname = input("Device two hostname: ")
        mgmt_vlan = input("Management VLAN: ")
        mgmt_ipv4gw = input("Management VLAN gateway (192.168.0.1/24): ")
        data = {
            "hostname": dev1_hostname,
            "platform": self.platform,
            "state": "MANAGED",
            "device_type": "DIST"
        }
        r = self.session.post(f"{self.url}/api/v1.0/device", json=data)
        if r.status_code != 200:
            raise Exception("Could not add first dist device")
        data["hostname"] = dev2_hostname
        r = self.session.post(f"{self.url}/api/v1.0/device", json=data)
        if r.status_code != 200:
            raise Exception("Could not add second dist device")
        data = {
            "device_a": dev1_hostname,
            "device_b": dev2_hostname,
            "ipv4_gw": mgmt_ipv4gw,
            "vlan": mgmt_vlan
        }
        r = self.session.post(f"{self.url}/api/v1.0/mgmtdomains", json=data)
        if r.status_code != 200:
            raise Exception("Could not add mgmtdomain")

        print("-"*80)
        return [dev1_hostname, dev2_hostname]

    def add_uplinks(self, devices):
        for hostname in devices:
            print("-" * 80)
            print(f"Adding uplinks for device {hostname}")
            while True:
                intf = input("Select interface name to add as uplink (or empty/enter to stop, ex Ethernet48): ")
                if not intf:
                    break
                neigh = input("What neighbor does this interface connect to? (ex cn-core-1): ")
                neigh_intf = input("What interface is used on the neighboring device for this link? (ex Ethernet1): ")
                data = {
                    "device_a": hostname,
                    "device_a_port": intf,
                    "device_b": neigh,
                    "device_b_port": neigh_intf
                }
                r = self.session.post(f"{self.url}/api/v1.0/linknets", json=data)
                print("Output: {}".format(r.json()))

            print("-" * 80)

    def generate_routingyaml(self):
        data = {
            "underlay": {
                "infra_link_net": "10.198.0.0/16",
                "infra_lo_net": "10.199.0.0/16",
                "mgmt_lo_net": self.mgmt_lo_net
            },
            "evpn_spines": []
        }
        for hostname in self.evpn_spines:
            data['evpn_spines'].append(hostname)
        print("Create the following file global/routing.yml in your settings repository")
        print("Paste the following yaml configuration into the file:")
        print("="*80)
        print(yaml.dump(data))
        print("="*80)
        self.update_settings()

    def update_settings(self):
        print("Commit and push the updates to the settings git repository now")
        input("Press any key when changes have been pushed and you are ready to continue")
        r = self.session.put(f"{self.url}/api/v1.0/repository/settings", json={"action": "refresh"})
        print("Output: {}".format(r.json()))

    def print_config(self):
        for hostname in self.devices:
            r = self.session.get(f"{self.url}/api/v1.0/device/{hostname}/generate_config")
            if r.status_code == 200:
                print(f"Paste below config to device {hostname}:")
                print("="*80)
                print(r.json()['data']['config']['generated_config'])
                print("="*80)


if __name__ == "__main__":
    newfabric = InitFabric()
    newfabric.pre_check()
    newfabric.generate_routingyaml()
    newfabric.add_devices()
    newfabric.print_config()