#!/usr/bin/env python3

import requests
import time
import unittest
import os
import datetime


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
    @classmethod
    def setUpClass(cls):
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
        assert False, "Failed to test connection to API"

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

    def test_00_sync(self):
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

    def test_01_init_dist(self):
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
        self.assertEqual(r.status_code, 200, "Failed to add mgmtdomain")

    def test_02_ztp(self):
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

    def test_03_interfaces(self):
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

    def test_04_syncto_access(self):
        r = requests.post(
            f'{URL}/api/v1.0/device_syncto',
            headers=AUTH_HEADER,
            json={"hostname": "eosaccess", "dry_run": True, "force": True},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to do sync_to access")
        self.check_jobid(r.json()['job_id'])
        r = requests.post(
            f'{URL}/api/v1.0/device_syncto',
            headers=AUTH_HEADER,
            json={"hostname": "eosaccess", "dry_run": True, "auto_push": True},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to do sync_to access")
        self.check_jobid(r.json()['job_id'])

    def test_05_syncto_dist(self):
        r = requests.post(
            f'{URL}/api/v1.0/device_syncto',
            headers=AUTH_HEADER,
            json={"hostname": "eosdist1", "dry_run": True, "force": True},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to do sync_to dist")
        self.check_jobid(r.json()['job_id'])

    def test_06_genconfig(self):
        r = requests.get(
            f'{URL}/api/v1.0/device/eosdist1/generate_config',
            headers=AUTH_HEADER,
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to generate config for eosdist1")

    def test_07_plugins(self):
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

    def test_08_firmware(self):
        r = requests.get(
            f'{URL}/api/v1.0/firmware',
            headers=AUTH_HEADER,
            verify=TLS_VERIFY
        )
        # TODO: not working
        #self.assertEqual(r.status_code, 200, "Failed to list firmware")

    def test_09_sysversion(self):
        r = requests.get(
            f'{URL}/api/v1.0/system/version',
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to get CNaaS-NMS version")

    def test_10_get_prev_config(self):
        hostname = "eosaccess"
        r = requests.get(
            f"{URL}/api/v1.0/device/{hostname}/previous_config?previous=0",
            headers=AUTH_HEADER,
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200)
        prev_job_id = r.json()['data']['job_id']
        if r.json()['data']['failed']:
            return
        data = {
            "job_id": prev_job_id,
            "dry_run": True
        }
        r = requests.post(
            f"{URL}/api/v1.0/device/{hostname}/previous_config",
            headers=AUTH_HEADER,
            verify=TLS_VERIFY,
            json=data
        )
        self.assertEqual(r.status_code, 200)
        restore_job_id = r.json()['job_id']
        job = self.check_jobid(restore_job_id)
        self.assertFalse(job['result']['devices'][hostname]['failed'])

    def test_11_update_facts_dist(self):
        hostname = "eosdist1"
        r = requests.post(
            f'{URL}/api/v1.0/device_update_facts',
            headers=AUTH_HEADER,
            json={"hostname": hostname},
            verify=TLS_VERIFY
        )
        self.assertEqual(r.status_code, 200, "Failed to do update facts for dist")
        restore_job_id = r.json()['job_id']
        job = self.check_jobid(restore_job_id)
        self.assertFalse(job['result']['devices'][hostname]['failed'])

    def test_12_abort_running_job(self):
        data = {
            'group': 'DIST',
            'url': '',
            'post_flight': True,
            'post_waittime': 30
        }
        result = requests.post(
            f"{URL}/api/v1.0/firmware/upgrade",
            headers=AUTH_HEADER,
            json=data,
            verify=TLS_VERIFY
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['status'], 'success')
        self.assertEqual(type(result.json()['job_id']), int)
        job_id: int = result.json()['job_id']
        time.sleep(2)
        result = requests.get(
            f'{URL}/api/v1.0/job/{job_id}',
            headers=AUTH_HEADER,
            verify=TLS_VERIFY
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['status'], 'success')
        self.assertEqual(len(result.json()['data']['jobs']), 1, "One job should be found")
        self.assertEqual(result.json()['data']['jobs'][0]['status'], "RUNNING",
                         "Job should be in RUNNING state at start")
        abort_data = {
            'action': 'ABORT',
            'abort_reason': 'unit test abort_running_job'
        }
        result = requests.put(
            f"{URL}/api/v1.0/job/{job_id}",
            headers=AUTH_HEADER,
            json=abort_data,
            verify=TLS_VERIFY
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['status'], 'success')
        result = requests.get(
            f'{URL}/api/v1.0/job/{job_id}',
            headers=AUTH_HEADER,
            verify=TLS_VERIFY
        )
        self.assertEqual(result.json()['data']['jobs'][0]['status'], "ABORTING",
                         "Job should be in ABORTING state after abort action")
        time.sleep(30)
        result = requests.get(
            f'{URL}/api/v1.0/job/{job_id}',
            headers=AUTH_HEADER,
            verify=TLS_VERIFY
        )
        self.assertEqual(result.json()['data']['jobs'][0]['status'], "ABORTED",
                         "Job should be in ABORTED state at end")

    def test_13_abort_scheduled_job(self):
        start_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)
        data = {
            'group': 'DIST',
            'url': '',
            'post_flight': True,
            'post_waittime': 30,
            'start_at': start_time.strftime('%Y-%m-%d %H:%M:%S')
        }
        result = requests.post(
            f"{URL}/api/v1.0/firmware/upgrade",
            headers=AUTH_HEADER,
            json=data,
            verify=TLS_VERIFY
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['status'], 'success')
        self.assertEqual(type(result.json()['job_id']), int)
        job_id: int = result.json()['job_id']
        time.sleep(2)
        result = requests.get(
            f'{URL}/api/v1.0/job/{job_id}',
            headers=AUTH_HEADER,
            verify=TLS_VERIFY
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['status'], 'success')
        self.assertEqual(len(result.json()['data']['jobs']), 1, "One job should be found")
        self.assertEqual(result.json()['data']['jobs'][0]['status'], "SCHEDULED",
                         "Job should be in SCHEDULED state at start")
        abort_data = {
            'action': 'ABORT',
            'abort_reason': 'unit test abort_scheduled_job'
        }
        result = requests.put(
            f"{URL}/api/v1.0/job/{job_id}",
            headers=AUTH_HEADER,
            json=abort_data,
            verify=TLS_VERIFY
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['status'], 'success')
        result = requests.get(
            f'{URL}/api/v1.0/job/{job_id}',
            headers=AUTH_HEADER,
            verify=TLS_VERIFY
        )
        self.assertEqual(result.json()['data']['jobs'][0]['status'], "ABORTED",
                         "Job should be in ABORTED state at end")


if __name__ == '__main__':
    unittest.main()
