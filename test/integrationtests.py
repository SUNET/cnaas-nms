#!/usr/bin/env python3

import requests
import time
import unittest


URL = "https://localhost"
TLS_VERIFY = False


if not TLS_VERIFY:
    import urllib3
    urllib3.disable_warnings()


class GetTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(self.wait_connect(), "Connection to API failed")

        r = requests.put(
            f'{URL}/api/v1.0/repository/templates',
            json={"action": "refresh"},
            verify=TLS_VERIFY
        )
        print("Template refresh status: {}".format(r.status_code))
        self.assertEqual(r.status_code, 200, "Failed to refresh templates")
        r = requests.put(
            f'{URL}/api/v1.0/repository/settings',
            json={"action": "refresh"},
            verify=TLS_VERIFY
        )
        print("Settings refresh status: {}".format(r.status_code))
        self.assertEqual(r.status_code, 200, "Failed to refresh settings")

    def wait_connect(self):
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

    def wait_for_discovered_device(self):
        for i in range(100):
            r = requests.get(
                f'{URL}/api/v1.0/device',
                params={'filter': 'state,DISCOVERED'},
                verify=TLS_VERIFY
            )
            if len(r.json()['data']['devices']) == 1:
                return r.json()['data']['devices'][0]['hostname'],\
                       r.json()['data']['devices'][0]['id']
            else:
                time.sleep(5)
        return None, None

    def check_jobid(self, job_id):
        for i in range(100):
            r = requests.get(
                f'{URL}/api/v1.0/job/{job_id}',
                verify=TLS_VERIFY
            )
            if r.status_code == 200:
                if r.json()['data']['jobs'][0]['status'] == 'FINISHED':
                    return r.json()['data']['jobs'][0]
                else:
                    time.sleep(5)
                    continue
            else:
                raise Exception

    def test_1_ztp(self):
        hostname, device_id = self.wait_for_discovered_device()
        print("Discovered hostname, id: {}, {}".format(hostname, device_id))
        self.assertTrue(hostname, "No device in state discovered found for ZTP")
        r = requests.post(
            f'{URL}/api/v1.0/device_init/{device_id}',
            json={"hostname": "eosaccess", "device_type": "ACCESS"},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to start device_init")
        self.assertEqual(r.json()['status'], 'success', "Failed to start device_init")
        step1_job_id = r.json()['job_id']
        step1_job_data = self.check_jobid(step1_job_id)
        result = step1_job_data['result']
        self.assertTrue(result['eosaccess'][0]['failed'],
                        "Expected failed result since mgmt_ip changed")
        time.sleep(5)
        step2_job_data = self.check_jobid(step1_job_data['next_job_id'])
        result_step2 = step2_job_data['result']
        self.assertFalse(result_step2['eosaccess'][0]['failed'],
                         "Could not reach device after ZTP")

    def test_2_syncto(self):
        r = requests.post(
            f'{URL}/api/v1.0/device_syncto',
            json={"hostname": "eosaccess", "dry_run": True},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to do sync_to")

    def test_3_interfaces(self):
        r = requests.get(
            f'{URL}/api/v1.0/device/eosaccess/interfaces',
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to get interfaces")

        r = requests.put(
            f'{URL}/api/v1.0/device/eosaccess/interfaces',
            json={"interfaces": {"Ethernet1": {"configtype": "ACCESS_AUTO"}}},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to update interface")


if __name__ == '__main__':
    unittest.main()
