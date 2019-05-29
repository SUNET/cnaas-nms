#!/usr/bin/env python3

import requests
import time

def wait_connect():
    for i in range(100):
        try:
            r = requests.put(
                'http://localhost:5000/api/v1.0/repository/templates',
                json={"action": "refresh"}
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

def main():
    if wait_connect():
        print("Success")
    else:
        print("Fail")

if __name__ == "__main__":
    main()

