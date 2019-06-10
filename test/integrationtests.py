#!/usr/bin/env python3

import requests
import time


def wait_connect():
    for i in range(100):
        try:
            r = requests.get(
                'http://localhost:5000/api/v1.0/device',
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
            'http://localhost:5000/api/v1.0/device',
            params={'filter': 'state,DISCOVERED'}
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
        'http://localhost:5000/api/v1.0/repository/templates',
        json={"action": "refresh"}
    )
    print("Template refresh status: {}".format(r.status_code))
    r = requests.put(
        'http://localhost:5000/api/v1.0/repository/settings',
        json={"action": "refresh"}
    )
    print("Settings refresh status: {}".format(r.status_code))
    discovered_hostname = wait_for_discovered_device()
    print("Discovered hostname: {}".format(discovered_hostname))


if __name__ == "__main__":
    main()

