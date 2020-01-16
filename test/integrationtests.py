#!/usr/bin/env python3

import requests
import time
import unittest
import os


if 'CNAASURL' in os.environ:
    URL = os.environ['CNAASURL']
else:
    URL = "https://localhost"
TLS_VERIFY = False
AUTH_HEADER = {"Authorization": "Bearer {}".format(os.environ['JWT_AUTH_TOKEN'])}


if not TLS_VERIFY:
    import urllib3
    urllib3.disable_warnings()


class GetTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(self.wait_connect(), "Connection to API failed")

        r = requests.put(
            f'{URL}/api/v1.0/repository/templates',
            headers=AUTH_HEADER,
            json={"action": "refresh"},
            verify=TLS_VERIFY
        )
        print("Template refresh status: {}".format(r.status_code))
        self.assertEqual(r.status_code, 200, "Failed to refresh templates")
        r = requests.put(
            f'{URL}/api/v1.0/repository/settings',
            headers=AUTH_HEADER,
            json={"action": "refresh"},
            verify=TLS_VERIFY
        )
        print("Settings refresh status: {}".format(r.status_code))
        self.assertEqual(r.status_code, 200, "Failed to refresh settings")

    def wait_connect(self):
        for i in range(100):
            try:
                r = requests.get(
                    f'{URL}/api/v1.0/devices',
                    headers=AUTH_HEADER,
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
                f'{URL}/api/v1.0/devices',
                headers=AUTH_HEADER,
                params={'filter[state]': 'DISCOVERED'},
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
                headers=AUTH_HEADER,
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

    def test_0_init_dist(self):
        new_dist_data = {
            "hostname": "eosdist1",
            "management_ip": "10.100.3.101",
            "platform": "eos",
            "state": "MANAGED",
            "device_type": "DIST"
        }
        r = requests.post(
            f'{URL}/api/v1.0/device',
            headers=AUTH_HEADER,
            json=new_dist_data,
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to add dist1")
        new_dist_data['hostname'] = "eosdist2"
        new_dist_data['management_ip'] = "10.100.3.102"
        r = requests.post(
            f'{URL}/api/v1.0/device',
            headers=AUTH_HEADER,
            json=new_dist_data,
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to add dist2")
        new_mgmtdom_data = {
            "ipv4_gw": "10.0.6.1/24",
            "device_a": "eosdist1",
            "device_b": "eosdist2",
            "vlan": 600
        }
        r = requests.post(
            f'{URL}/api/v1.0/mgmtdomains',
            headers=AUTH_HEADER,
            json=new_mgmtdom_data,
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to add dist2")

    def test_1_ztp(self):
        hostname, device_id = self.wait_for_discovered_device()
        print("Discovered hostname, id: {}, {}".format(hostname, device_id))
        self.assertTrue(hostname, "No device in state discovered found for ZTP")
        r = requests.post(
            f'{URL}/api/v1.0/device_init/{device_id}',
            headers=AUTH_HEADER,
            json={"hostname": "eosaccess", "device_type": "ACCESS"},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to start device_init")
        self.assertEqual(r.json()['status'], 'success', "Failed to start device_init")
        step1_job_id = r.json()['job_id']
        step1_job_data = self.check_jobid(step1_job_id)
        result = step1_job_data['result']
        self.assertTrue(result['devices']['eosaccess']['failed'],
                        "Expected failed result since mgmt_ip changed")
        time.sleep(5)
        step2_job_data = self.check_jobid(step1_job_data['next_job_id'])
        result_step2 = step2_job_data['result']
        self.assertFalse(result_step2['devices']['eosaccess']['failed'],
                         "Could not reach device after ZTP")

    def test_2_interfaces(self):
        r = requests.get(
            f'{URL}/api/v1.0/device/eosaccess/interfaces',
            headers=AUTH_HEADER,
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to get interfaces")

        r = requests.put(
            f'{URL}/api/v1.0/device/eosaccess/interfaces',
            headers=AUTH_HEADER,
            json={"interfaces": {"Ethernet1": {"configtype": "ACCESS_AUTO"}}},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to update interface")

        r = requests.put(
            f'{URL}/api/v1.0/device/eosaccess/interfaces',
            headers=AUTH_HEADER,
            json={"interfaces": {"Ethernet1": {"data": {"vxlan": "student1"}}}},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to update interface")

    def test_3_syncto_access(self):
        r = requests.post(
            f'{URL}/api/v1.0/device_syncto',
            headers=AUTH_HEADER,
            json={"hostname": "eosaccess", "dry_run": True, "force": True},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to do sync_to access")
        r = requests.post(
            f'{URL}/api/v1.0/device_syncto',
            headers=AUTH_HEADER,
            json={"hostname": "eosaccess", "dry_run": True, "auto_push": True},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to do sync_to access")

    def test_4_syncto_dist(self):
        r = requests.post(
            f'{URL}/api/v1.0/device_syncto',
            headers=AUTH_HEADER,
            json={"hostname": "eosdist1", "dry_run": True, "force": True},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to do sync_to dist")

    def test_5_genconfig(self):
        r = requests.get(
            f'{URL}/api/v1.0/device/eosdist1/generate_config',
            headers=AUTH_HEADER,
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to generate config for eosdist1")

    def test_6_plugins(self):
        r = requests.get(
            f'{URL}/api/v1.0/plugins',
            headers=AUTH_HEADER,
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to get running plugins")

        r = requests.put(
            f'{URL}/api/v1.0/plugins',
            headers=AUTH_HEADER,
            json={"action": "selftest"},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to run plugin selftests")

    def test_7_firmware(self):
        r = requests.get(
            f'{URL}/api/v1.0/firmware',
            headers=AUTH_HEADER,
            verify=TLS_VERIFY
        )
        # TODO: not working
        #self.assertEqual(r.status_code, 200, "Failed to list firmware")


if __name__ == '__main__':
    unittest.main()
