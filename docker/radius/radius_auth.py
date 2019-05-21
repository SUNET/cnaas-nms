#!/usr/bin/env python3

import sys
import requests

def accept():
    sys.exit(0)

def reject():
    sys.exit(-1)

def get_user(argv):
    url = argv[1]
    url += '/api/v1.0/auth'
    url += '?username={}&password={}'.format(argv[2], argv[3])
    try:
        response = requests.get(url)
        json = response.json()
    except Exception:
        reject()
    if response.status_code == 200:
        if 'attributes' in json['data']:
            for _ in json['data']['attributes'].split(','):
                print(_)
        accept()
    if 'status' not in json:
        reject()
    if 'message' not in json:
        reject()
    if json['status'] == 'error' and json['message'] == 'User not found':
        return -1
    else:
        reject()
    reject()

def post_user(argv):
    url = argv[1]
    url += '/api/v1.0/auth'
    json = {'username': argv[2], 'password': argv[3]}
    try:
        response = requests.post(url, json=json)
    except Exception:
        reject()
    if response.status_code != 200:
        reject()
    return 0

def main(argv):
    if len(argv) != 4:
        reject()
    if get_user(argv) == -1:
        if post_user(argv) != 0:
            reject()
        if get_user(argv) != 0:
            reject()
    reject()

if __name__ == '__main__':
    main(sys.argv)
