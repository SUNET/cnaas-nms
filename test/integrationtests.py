#!/usr/bin/env python3

import requests
import time


URL="https://localhost"
TLS_VERIFY=False


if not TLS_VERIFY:
    import urllib3
    urllib3.disable_warnings()


def wait_connect():
    for i in range(100):
        try:
            r = requests.get(
                f'{URL}/api/v1.0/device',
                verify=TLS_VERIFY
            )
        except Exception as e:
            print("Exception {}, retrying in 1 second".format(str(e)))
            time.sleep(1)
        else:
            if r.status_code == 200:
                return True
            else:
                print("Bad status code {}, retrying in 1 second...".format(r.status_code))
                time.sleep(1)
    return False


def wait_for_discovered_device():
    for i in range(100):
        r = requests.get(
            f'{URL}/api/v1.0/device',
            params={'filter': 'state,DISCOVERED'},
            verify=TLS_VERIFY
        )
        if len(r.json()['data']['devices']) == 1:
            return r.json()['data']['devices'][0]['hostname']
        else:
            time.sleep(1)
    return False


def main():
    if wait_connect():
        print("Success")
    else:
        print("Fail")
        return

    r = requests.put(
        f'{URL}/api/v1.0/repository/templates',
        json={"action": "refresh"},
        verify=TLS_VERIFY
    )
    print("Template refresh status: {}".format(r.status_code))
    r = requests.put(
        f'{URL}/api/v1.0/repository/settings',
        json={"action": "refresh"},
        verify=TLS_VERIFY
    )
    print("Settings refresh status: {}".format(r.status_code))
    discovered_hostname = wait_for_discovered_device()
    print("Discovered hostname: {}".format(discovered_hostname))


if __name__ == "__main__":
    main()

