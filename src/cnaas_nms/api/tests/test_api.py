import shutil
import yaml
import pkg_resources
import os

import unittest
import pytest
import cnaas_nms.api.app
from cnaas_nms.api.tests.app_wrapper import TestAppWrapper
from cnaas_nms.app_settings import app_settings


@pytest.mark.integration
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
        hostname = self.testdata['managed_dist']
        result = self.client.get(
            f'/api/v1.0/devices',
            query_string={"filter[hostname]": hostname}
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

    def test_filter_job(self):
        result = self.client.get('/api/v1.0/jobs?filter[function.name][contains]=sync&filter_jobresult=config')

        # 200 OK
        self.assertEqual(result.status_code, 200)
        # Succes in json
        self.assertEqual(result.json['status'], 'success')
        # At least one result
        self.assertGreaterEqual(len(result.json['data']['jobs']), 1, "No jobs found")
        # Exactly 2 task results
        first_device_result = next(iter(result.json['data']['jobs'][0]['result']['devices'].values()))
        self.assertEqual(len(first_device_result['job_tasks']), 2,
                         "Job result output should only contain 2 tasks")
        self.assertEqual(len(list(filter(lambda x: x["task_name"] != "Generate device config",
                                         first_device_result['job_tasks']))),
                         2, "Job result included 'Generate device config' task")

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

    def test_update_managementdomain(self):
        result = self.client.get('/api/v1.0/mgmtdomains?per_page=1')
        self.assertIsInstance(result.json['data']['mgmtdomains'][0]['id'], int)
        id = result.json['data']['mgmtdomains'][0]['id']
        data = {"vlan": 601}
        result = self.client.put('/api/v1.0/mgmtdomain/{}'.format(id), json=data)
        self.assertEqual(result.status_code, 200)
        self.assertIn('updated_mgmtdomain', result.json['data'])
        # Make sure returned data inclueds new vlan
        self.assertEqual(result.json['data']['updated_mgmtdomain']['vlan'], data['vlan'])
        # Change back to old vlan
        data["vlan"] = 600
        result = self.client.put('/api/v1.0/mgmtdomain/{}'.format(id), json=data)
        self.assertEqual(result.status_code, 200)
        self.assertIn('updated_mgmtdomain', result.json['data'])
        # Check that no change is made when applying same vlan twice
        data["vlan"] = 600
        result = self.client.put('/api/v1.0/mgmtdomain/{}'.format(id), json=data)
        self.assertEqual(result.status_code, 200)
        self.assertIn('unchanged_mgmtdomain', result.json['data'])

    def test_validate_managementdomain(self):
        result = self.client.get('/api/v1.0/mgmtdomains?per_page=1')
        self.assertIsInstance(result.json['data']['mgmtdomains'][0]['id'], int)
        id = result.json['data']['mgmtdomains'][0]['id']
        # Check that you get error if using invalid gw
        data = {"ipv4_gw": "10.0.6.0/24"}
        result = self.client.put('/api/v1.0/mgmtdomain/{}'.format(id), json=data)
        self.assertEqual(result.status_code, 400)
        # Check that you get error if using invalid vlan id
        data = {"vlan": 5000}
        result = self.client.put('/api/v1.0/mgmtdomain/{}'.format(id), json=data)
        self.assertEqual(result.status_code, 400)

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
        # Delete everything inside setting repo
        for filename in os.listdir(app_settings.SETTINGS_LOCAL):
            file_path = os.path.join(app_settings.SETTINGS_LOCAL, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)

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

    def test_update_interface_data_neighbor(self):
        ifname = self.testdata['interface_update']
        data = {
            "interfaces": {
                ifname: {
                    "data": {
                        "neighbor_id": 123,
                        "neighbor": "testhostname"
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
        self.assertEqual(ifname in result.json['data']['updated'], True)
        # Reset
        data['interfaces'][ifname]['data']['neighbor_id'] = None
        data['interfaces'][ifname]['data']['neighbor'] = None
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

    @pytest.mark.equipment
    def test_get_interface_status(self):
        result = self.client.get(
            "/api/v1.0/device/{}/interface_status".format(self.testdata['interface_device'])
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
        self.assertEqual('interface_status' in result.json['data'], True)

    @pytest.mark.equipment
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

    def test_get_groups(self):
        groupname = self.testdata['groupname']
        result = self.client.get("/api/v1.0/groups")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
        self.assertTrue(groupname in result.json['data']['groups'],
                        f"Group '{groupname}' not found")
        self.assertGreaterEqual(len(result.json['data']['groups'][groupname]), 1,
                                f"No devices found in group '{groupname}'")

    def test_get_groups_osversion(self):
        groupname = self.testdata['groupname']
        result = self.client.get(f"/api/v1.0/groups/{groupname}/os_version")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
        self.assertGreaterEqual(len(result.json['data']['groups'][groupname]), 1,
                                f"No devices found in group '{groupname}' os_versions")

    def test_renew_cert_errors(self):
        # Test invalid hostname
        data = {"hostname": "...", "action": "RENEW"}
        result = self.client.post('/api/v1.0/device_cert', json=data)
        self.assertEqual(result.status_code, 400)

        # Test invalid action
        data = {"hostname": self.testdata['managed_dist']}
        result = self.client.post('/api/v1.0/device_cert', json=data)
        self.assertEqual(result.status_code, 400)
        self.assertTrue("action" in result.json['message'], msg="Unexpected error message")

    def test_generate_only_vars(self):
        result = self.client.get("/api/v1.0/device/{}/generate_config".format(
            self.testdata['interface_device']
        ))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['status'], 'success')
        self.assertEqual(
            result.json['data']['config']['available_variables']['hostname'],
            self.testdata['interface_device'],
            "hostname variable not found in generate_only variables"
        )

    def test_linknet(self):
        post_data = {
            "device_a": "eosdist1",
            "device_a_port": "Ethernet3",
            "device_b": "eosdist2",
            "device_b_port": "Ethernet3"
        }
        result = self.client.post('/api/v1.0/linknets', json=post_data)
        self.assertEqual(result.status_code, 201, "Bad status code on POST")
        self.assertEqual(result.json['status'], 'success')
        self.assertIsInstance(result.json['data']['id'], int)
        self.assertIsInstance(result.json['data']['ipv4_network'], str)
        self.assertTrue("/" in result.json['data']['ipv4_network'])
        linknet_id: int = result.json['data']['id']

        result = self.client.get('/api/v1.0/linknet/{}'.format(linknet_id))
        self.assertEqual(result.status_code, 200, "Bad status code on GET")
        self.assertEqual(result.json['status'], 'success')
        self.assertEqual(len(result.json['data']['linknets']), 1)
        self.assertIsInstance(result.json['data']['linknets'][0]['id'], int)
        self.assertEqual(result.json['data']['linknets'][0]['id'], linknet_id)

        result = self.client.get('/api/v1.0/linknets')
        self.assertEqual(result.status_code, 200, "Bad status code on GET all linknets")
        self.assertEqual(result.json['status'], 'success')
        self.assertGreaterEqual(len(result.json['data']['linknets']), 1,
                                "Less than one linknet found on GET linknets")

        put_data = {
            "ipv4_network": "10.198.0.0/31",
            "device_a_ip": "10.198.0.0",
            "device_b_ip": "10.198.0.1",
        }
        result = self.client.put('/api/v1.0/linknet/{}'.format(linknet_id), json=put_data)
        self.assertEqual(result.status_code, 200, "Bad status code on PUT with OK data")
        self.assertIn("updated_linknet", result.json['data'])
        put_data['device_b_ip'] = "10.198.0.0"  # Bad data
        result = self.client.put('/api/v1.0/linknet/{}'.format(linknet_id), json=put_data)
        self.assertEqual(result.status_code, 400, "Bad status code on PUT with bad data")
        self.assertEqual(result.json['status'], 'error')

        result = self.client.delete('/api/v1.0/linknet/{}'.format(linknet_id))
        self.assertEqual(result.status_code, 200, "Bad status code on DELETE")
        self.assertEqual(result.json['status'], 'success')
        self.assertIsInstance(result.json['data']['deleted_linknet']['id'], int)
        self.assertEqual(result.json['data']['deleted_linknet']['id'], linknet_id)


def test_add_new_device(client, redis, postgresql, settings_directory):
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
    result = client.post('/api/v1.0/device', json=data)
    print(result.json)
    assert result.status_code == 200
    assert result.json['status'] == 'success'


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def app(jwt_auth_token):
    the_app = cnaas_nms.api.app.app
    the_app.wsgi_app = TestAppWrapper(the_app.wsgi_app, jwt_auth_token)
    return the_app


@pytest.fixture
def jwt_auth_token():
    data_dir = pkg_resources.resource_filename(__name__, 'data')
    with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
        testdata = yaml.safe_load(f_testdata)
        return testdata.get('jwt_auth_token')


if __name__ == '__main__':
    unittest.main()
