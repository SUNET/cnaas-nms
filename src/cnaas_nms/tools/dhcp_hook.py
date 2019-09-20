#!/usr/bin/env python3

import sys

import requests
import yaml

import cnaas_nms.db.helper
from cnaas_nms.tools.log import get_logger


logger = get_logger()


def get_apidata(configfile='/etc/cnaas-nms/apiclient.yml'):
    with open(configfile, 'r') as apiclient_file:
        return yaml.safe_load(apiclient_file)


def main() -> int:
    if len(sys.argv) < 3:
        return 1
    if sys.argv[1] == "commit":
        try:
            ztp_mac = cnaas_nms.db.helper.canonical_mac(sys.argv[2])
            dhcp_ip = sys.argv[3]
            platform = sys.argv[4]
        except Exception as e:
            print(str(e))
            return 2

        apidata = get_apidata()
        base_url = apidata['cnaas_nms']['base_url']
        verify_tls = apidata['cnaas_nms']['verify_tls']
        params = {'filter[ztp_mac]': ztp_mac}
        r = requests.get(f"{base_url}/api/v1.0/devices", params=params, verify=verify_tls)
        if r.status_code != 200:
            logger.error("Could not query device API: {} (status {})".format(
                r.text, r.status_code))
            return 10
        try:
            r_data = r.json()
            if 'status' not in r_data or 'data' not in r_data:
                raise ValueError("No status key in json data")
        except Exception as e:
            logger.error("Invalid JSON response from devices API: {}".format(r.text))
            return 11
        if r_data['status'] != "success":
            logger.error("Could not query device API: {} (status {})".format(r.text, r_data['status']))
            return 12
        devices = r_data['data']['devices']
        if devices:
            dev_dict: dict = devices[0]
            dev_id: int = int(dev_dict['id'])
            if dev_dict['state'] == 'DHCP_BOOT':
                data = {"ztp_mac": ztp_mac, "dhcp_ip": dhcp_ip}
                r = requests.post(f"{base_url}/api/v1.0/device_discover", json=data, verify=verify_tls)
                if r.status_code != 200:
                    logger.error("Error when scheduling job to discover device: {} ({})".format(
                        r.text, r.status_code
                    ))
                    return 20
                try:
                    r_data = r.json()
                    if 'status' not in r_data or 'job_id' not in r_data:
                        raise ValueError("No status key in json data")
                except Exception as e:
                    logger.error("Invalid JSON response from device_discover API: {}".format(r.text))
                    return 21

                logger.info("Device in state DHCP_BOOT acquired new lease, " +
                            "scheduling job id {} to discover device".format(
                                r_data['job_id']
                            ))
            elif dev_dict['state'] == 'DISCOVERED':
                if dev_dict['dhcp_ip'] != dhcp_ip:
                    data = {"dhcp_ip": dhcp_ip}
                    r = requests.put(f"{base_url}/api/v1.0/device/{dev_id}", json=data, verify=verify_tls)
                    logger.info(
                        "Updating DHCP IP for device with ZTP MAC {} to: {} (status {})".format(
                            ztp_mac, dhcp_ip, r.status_code
                        ))
            else:
                logger.error(
                    "Device with ztp_mac {} in state {} unexpectedly booted via DHCP ({})".format(
                        ztp_mac,
                        dev_dict['state'],
                        dhcp_ip
                    ))

        else:
            # Add new device
            logger.info("New device booted via DHCP to state DHCP_BOOT: {}".
                        format(ztp_mac))
            data = {
                "ztp_mac": ztp_mac,
                "dhcp_ip": dhcp_ip,
                "hostname": f'mac-{ztp_mac}',
                "platform": platform,
                "state": "DHCP_BOOT",
                "device_type": "UNKNOWN"
            }
            r = requests.post(f"{base_url}/api/v1.0/device", json=data, verify=verify_tls)
            if r.status_code != 200:
                logger.error("Error when adding new device: {} ({})".format(
                    r.text, r.status_code
                ))
                return 30
            try:
                r_data = r.json()
                if 'status' not in r_data or 'data' not in r_data:
                    raise ValueError("No status key in json data")
            except Exception as e:
                logger.error("Invalid JSON response from POST to device API: {}".format(r.text))
                return 31
            logger.info("Added new device with hostname {} as id {} in device database".format(
                r_data['data']['added_device']['hostname'],
                r_data['data']['added_device']['id']
            ))


if __name__ == '__main__':
    sys.exit(main())
