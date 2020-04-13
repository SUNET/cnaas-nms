import shutil
import yaml
import pkg_resources
import os
import time

import unittest
import cnaas_nms.api.app
from cnaas_nms.api.tests.app_wrapper import TestAppWrapper


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.jwt_auth_token = None
        data_dir = pkg_resources.resource_filename(__name__, 'data')
        with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
            self.testdata = yaml.safe_load(f_testdata)
            if 'jwt_auth_token' in self.testdata:
                self.jwt_auth_token = self.testdata['jwt_auth_token']
        self.app = cnaas_nms.api.app.app
        self.app.wsgi_app = TestAppWrapper(self.app.wsgi_app, self.jwt_auth_token)
        self.client = self.app.test_client()

    def test_get_single_device(self):
        hostname = "eosdist1"
        result = self.client.get(
            f'/api/v1.0/devices',
            params={"filter[hostname]": hostname}
        )

        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Succes in json
        self.assertEqual(result.json['status'], 'success')
        # Exactly one result
        self.assertEqual(len(result.json['data']['devices']), 1)
        # The one result should have the same ID we asked for
        self.assertEqual(result.json['data']['devices'][0]['hostname'], hostname)

    def test_get_last_job(self):
        result = self.client.get('/api/v1.0/jobs?per_page=1')

        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Succes in json
        self.assertEqual(result.json['status'], 'success')
        # Exactly one result
        self.assertEqual(len(result.json['data']['jobs']), 1)

    def test_get_managementdomain(self):
        result = self.client.get('/api/v1.0/mgmtdomains?per_page=1')
        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Succes in json
        self.assertEqual(result.json['status'], 'success')
        # Exactly one result
        self.assertEqual(len(result.json['data']['mgmtdomains']), 1)
        # The one result should have the same ID we asked for
        self.assertIsInstance(result.json['data']['mgmtdomains'][0]['id'], int)

    def test_repository_refresh(self):
        data = {"action": "refresh"}
        result = self.client.put('/api/v1.0/repository/settings', json=data)
        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Succes in json
        self.assertEqual(result.json['status'], 'success')
        # Exactly one result
        self.assertRegex(result.json['data'], r'[Cc]ommit')

    def test_repository_get(self):
        # Delete settings repo
        with open('/etc/cnaas-nms/repository.yml', 'r') as db_file:
            repo_config = yaml.safe_load(db_file)
        shutil.rmtree(repo_config['settings_local'])

        # Check that no repo is found
        result = self.client.get('/api/v1.0/repository/settings')
        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Succes in json
        self.assertEqual(result.json['status'], 'success')
        # Exactly one result
        self.assertEqual(result.json['data'], "Repository is not yet cloned from remote")

        # Refresh repo
        self.test_repository_refresh()

        # Check that repo has a commit after the refresh
        result = self.client.get('/api/v1.0/repository/settings')
        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Succes in json
        self.assertEqual(result.json['status'], 'success')
        # Exactly one result
        self.assertRegex(result.json['data'], r'[Cc]ommit')

    def test_sync_devices_invalid_input(self):
        # Test invalid hostname
        data = {"hostname": "...", "dry_run": True}
        result = self.client.post('/api/v1.0/device_syncto', json=data)
        self.assertEqual(result.status_code, 400)

        # Test invalid device_type
        data = {"device_type": "nonexistent", "dry_run": True}
        result = self.client.post('/api/v1.0/device_syncto', json=data)
        self.assertEqual(result.status_code, 400)

    def test_sync_devices(self):
        # Test dry run sync of all devices
        data = {"all": True, "dry_run": True}
        result = self.client.post('/api/v1.0/device_syncto', json=data)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
        self.assertEqual(type(result.json['job_id']), int)

    def test_get_interfaces(self):
        result = self.client.get("/api/v1.0/device/{}/interfaces".format(
            self.testdata['interface_device']
        ))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')

    def test_update_interface_configtype(self):
        ifname = self.testdata['interface_update']
        data = {
            "interfaces": {
                ifname: {
                    "configtype": "ACCESS_UNTAGGED"
                }
            }
        }
        result = self.client.put(
            "/api/v1.0/device/{}/interfaces".format(self.testdata['interface_device']),
            json=data
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
#        self.assertEqual(ifname in result.json['data']['updated'], True)
        # Change back
        data['interfaces'][ifname]['configtype'] = "ACCESS_AUTO"
        result = self.client.put(
            "/api/v1.0/device/{}/interfaces".format(self.testdata['interface_device']),
            json=data
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
        self.assertEqual(ifname in result.json['data']['updated'], True)

    def test_update_interface_data_untagged(self):
        # Test untagged_vlan
        ifname = self.testdata['interface_update']
        data = {
            "interfaces": {
                ifname: {
                    "data": {
                        "untagged_vlan": self.testdata['untagged_vlan']
                    }
                }
            }
        }
        result = self.client.put(
            "/api/v1.0/device/{}/interfaces".format(self.testdata['interface_device']),
            json=data
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
#        self.assertEqual(ifname in result.json['data']['updated'], True)
        # Test invalid
        data['interfaces'][ifname]['data']['untagged_vlan'] = "thisshouldnetexist"
        result = self.client.put(
            "/api/v1.0/device/{}/interfaces".format(self.testdata['interface_device']),
            json=data
        )
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.json['status'], 'error')

    def test_update_interface_data_tagged(self):
        # Test tagged
        ifname = self.testdata['interface_update']
        data = {
            "interfaces": {
                ifname: {
                    "data": {
                        "tagged_vlan_list": self.testdata['tagged_vlan_list']
                    }
                }
            }
        }
        result = self.client.put(
            "/api/v1.0/device/{}/interfaces".format(self.testdata['interface_device']),
            json=data
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
#        self.assertEqual(ifname in result.json['data']['updated'], True)
        # Test invalid
        data['interfaces'][ifname]['data']['tagged_vlan_list'] = ["thisshouldnetexist"]
        result = self.client.put(
            "/api/v1.0/device/{}/interfaces".format(self.testdata['interface_device']),
            json=data
        )
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.json['status'], 'error')

    def test_update_interface_data_description(self):
        # Reset descr
        ifname = self.testdata['interface_update']
        data = {
            "interfaces": {
                ifname: {
                    "data": {
                        "description": None
                    }
                }
            }
        }
        result = self.client.put(
            "/api/v1.0/device/{}/interfaces".format(self.testdata['interface_device']),
            json=data
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
        # Update descr
        data['interfaces'][ifname]['data']['description'] = "Test update description"
        result = self.client.put(
            "/api/v1.0/device/{}/interfaces".format(self.testdata['interface_device']),
            json=data
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
        self.assertEqual(ifname in result.json['data']['updated'], True)

    def test_update_interface_data_enabled(self):
        # Disable interface
        ifname = self.testdata['interface_update']
        data = {
            "interfaces": {
                ifname: {
                    "data": {
                        "enabled": False
                    }
                }
            }
        }
        result = self.client.put(
            "/api/v1.0/device/{}/interfaces".format(self.testdata['interface_device']),
            json=data
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
        # Enable interface
        data['interfaces'][ifname]['data']['enabled'] = True
        result = self.client.put(
            "/api/v1.0/device/{}/interfaces".format(self.testdata['interface_device']),
            json=data
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
        self.assertEqual(ifname in result.json['data']['updated'], True)

    def test_add_new_device(self):
        data = {
            "hostname": "unittestdevice",
            "site_id": 1,
            "description": '',
            "management_ip": "10.1.2.3",
            "dhcp_ip": "11.1.2.3",
            "serial": '',
            "ztp_mac": "0800275C091F",
            "platform": "eos",
            "vendor": '',
            "model": '',
            "os_version": '',
            "state": "MANAGED",
            "device_type": "ACCESS",
        }
        result = self.client.post('/api/v1.0/device', json=data)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')

    def test_get_joblocks(self):
        result = self.client.get('/api/v1.0/joblocks')

        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Success in json
        self.assertEqual(result.json['status'], 'success')
        # Exactly one result
        #self.assertEqual(len(result.json['data']['jobs']), 1)

    def test_get_interface_status(self):
        result = self.client.get(
            "/api/v1.0/device/{}/interface_status".format(self.testdata['interface_device'])
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
        self.assertEqual('interface_status' in result.json['data'], True)

    def test_bounce_interface(self):
        # Bounce of uplink should give error 400
        data = {'bounce_interfaces': [self.testdata['interface_uplink']]}
        result = self.client.put(
            "/api/v1.0/device/{}/interface_status".format(self.testdata['interface_device']),
            json=data
        )
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.json['status'], 'error')
        # Bounce of non-existing interface should give error 400
        data = {'bounce_interfaces': ['Ethernet999']}
        result = self.client.put(
            "/api/v1.0/device/{}/interface_status".format(self.testdata['interface_device']),
            json=data
        )
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.json['status'], 'error')
        # Try to bounce client interface
        data = {'bounce_interfaces': [self.testdata['interface_update']]}
        result = self.client.put(
            "/api/v1.0/device/{}/interface_status".format(self.testdata['interface_device']),
            json=data
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')


if __name__ == '__main__':
    unittest.main()
