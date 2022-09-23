import re
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
class TestApi:
    def test_get_single_device(self, client, testdata):
        hostname = testdata['managed_dist']
        result = client.get(f'/api/v1.0/devices', query_string={"filter[hostname]": hostname})
        print(result.json)

        # 200 OK
        assert result.status_code == 200
        # Success in json
        assert result.json['status'] == 'success'
        # Exactly one result
        assert len(result.json['data']['devices']) == 1
        # The one result should have the same ID we asked for
        assert result.json['data']['devices'][0]['hostname'] == hostname

    def test_get_last_job(self, client):
        result = client.get('/api/v1.0/jobs?per_page=1')
        print(result.json)

        # 200 OK
        assert result.status_code == 200
        # Success in json
        assert result.json['status'] == 'success'
        # Exactly one result
        assert len(result.json['data']['jobs']) == 1

    def test_filter_job(self, client):
        result = client.get(
            '/api/v1.0/jobs?filter[function.name][contains]=sync&filter_jobresult=config'
        )
        print(result.json)

        # 200 OK
        assert result.status_code == 200
        # Success in json
        assert result.json['status'] == 'success'
        # At least one result
        assert len(result.json['data']['jobs']) >= 1, "No jobs found"
        # Exactly 2 task results
        first_device_result = next(
            iter(result.json['data']['jobs'][0]['result']['devices'].values())
        )
        assert (
            len(first_device_result['job_tasks']) == 2
        ), "Job result output should only contain 2 tasks"
        assert (
            len(
                list(
                    filter(
                        lambda x: x["task_name"] != "Generate device config",
                        first_device_result['job_tasks'],
                    )
                )
            )
            == 2
        ), "Job result included 'Generate device config' task"

    def test_get_managementdomain(self, client):
        result = client.get('/api/v1.0/mgmtdomains?per_page=1')
        print(result.json)

        # 200 OK
        assert result.status_code == 200
        # Success in json
        assert result.json['status'] == 'success'
        # Exactly one result
        assert len(result.json['data']['mgmtdomains']) == 1
        # The one result should have the same ID we asked for
        assert isinstance(result.json['data']['mgmtdomains'][0]['id'], int)

    def test_update_managementdomain(self, client):
        result = client.get('/api/v1.0/mgmtdomains?per_page=1')
        assert isinstance(result.json['data']['mgmtdomains'][0]['id'], int)
        id = result.json['data']['mgmtdomains'][0]['id']
        data = {"vlan": 601}
        result = client.put('/api/v1.0/mgmtdomain/{}'.format(id), json=data)
        assert result.status_code == 200
        assert 'updated_mgmtdomain' in result.json['data']
        # Make sure returned data inclueds new vlan
        assert result.json['data']['updated_mgmtdomain']['vlan'] == data['vlan']
        # Change back to old vlan
        data["vlan"] = 600
        result = client.put('/api/v1.0/mgmtdomain/{}'.format(id), json=data)
        assert result.status_code == 200
        assert 'updated_mgmtdomain' in result.json['data']
        # Check that no change is made when applying same vlan twice
        data["vlan"] = 600
        result = client.put('/api/v1.0/mgmtdomain/{}'.format(id), json=data)
        assert result.status_code == 200
        assert 'unchanged_mgmtdomain' in result.json['data']

    def test_validate_managementdomain(self, client):
        result = client.get('/api/v1.0/mgmtdomains?per_page=1')
        assert isinstance(result.json['data']['mgmtdomains'][0]['id'], int)
        id = result.json['data']['mgmtdomains'][0]['id']
        # Check that you get error if using invalid gw
        data = {"ipv4_gw": "10.0.6.0/24"}
        result = client.put('/api/v1.0/mgmtdomain/{}'.format(id), json=data)
        assert result.status_code == 400
        # Check that you get error if using invalid vlan id
        data = {"vlan": 5000}
        result = client.put('/api/v1.0/mgmtdomain/{}'.format(id), json=data)
        assert result.status_code == 400

    def test_repository_refresh(self, client):
        data = {"action": "refresh"}
        result = client.put('/api/v1.0/repository/settings', json=data)
        # 200 OK
        assert result.status_code == 200
        # Success in json
        assert result.json['status'] == 'success'
        # Exactly one result
        assert re.match(r'[Cc]ommit', result.json['data'])

    def test_repository_get(self, client):
        # Delete everything inside setting repo
        for filename in os.listdir(app_settings.SETTINGS_LOCAL):
            file_path = os.path.join(app_settings.SETTINGS_LOCAL, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)

        # Check that no repo is found
        result = client.get('/api/v1.0/repository/settings')
        # 200 OK
        assert result.status_code == 200
        # Success in json
        assert result.json['status'] == 'success'
        # Exactly one result
        assert result.json['data'] == "Repository is not yet cloned from remote"

        # Refresh repo
        data = {"action": "refresh"}
        client.put('/api/v1.0/repository/settings', json=data)

        # Check that repo has a commit after the refresh
        result = client.get('/api/v1.0/repository/settings')
        # 200 OK
        assert result.status_code == 200
        # Success in json
        assert result.json['status'] == 'success'
        # Exactly one result
        assert re.match(r'[Cc]ommit', result.json['data'])

    def test_sync_devices_invalid_input(self, client):
        # Test invalid hostname
        data = {"hostname": "...", "dry_run": True}
        result = client.post('/api/v1.0/device_syncto', json=data)
        assert result.status_code == 400

        # Test invalid device_type
        data = {"device_type": "nonexistent", "dry_run": True}
        result = client.post('/api/v1.0/device_syncto', json=data)
        assert result.status_code == 400

    def test_sync_devices(self, client):
        # Test dry run sync of all devices
        data = {"all": True, "dry_run": True}
        result = client.post('/api/v1.0/device_syncto', json=data)
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        assert isinstance(result.json['job_id'], int)

    def test_get_interfaces(self, client, testdata):
        result = client.get("/api/v1.0/device/{}/interfaces".format(testdata['interface_device']))
        assert result.status_code == 200
        assert result.json['status'] == 'success'

    def test_update_interface_configtype(self, client, testdata):
        ifname = testdata['interface_update']
        data = {"interfaces": {ifname: {"configtype": "ACCESS_UNTAGGED"}}}
        result = client.put(
            "/api/v1.0/device/{}/interfaces".format(testdata['interface_device']), json=data
        )
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        #        self.assertEqual(ifname in result.json['data']['updated'], True)
        # Change back
        data['interfaces'][ifname]['configtype'] = "ACCESS_AUTO"
        result = client.put(
            "/api/v1.0/device/{}/interfaces".format(testdata['interface_device']), json=data
        )
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        assert ifname in result.json['data']['updated']

    def test_update_interface_data_untagged(self, client, testdata):
        # Test untagged_vlan
        ifname = testdata['interface_update']
        data = {"interfaces": {ifname: {"data": {"untagged_vlan": testdata['untagged_vlan']}}}}
        result = client.put(
            "/api/v1.0/device/{}/interfaces".format(testdata['interface_device']), json=data
        )
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        #        self.assertEqual(ifname in result.json['data']['updated'], True)
        # Test invalid
        data['interfaces'][ifname]['data']['untagged_vlan'] = "thisshouldnetexist"
        result = client.put(
            "/api/v1.0/device/{}/interfaces".format(testdata['interface_device']), json=data
        )
        assert result.status_code == 400
        assert result.json['status'] == 'error'

    def test_update_interface_data_tagged(self, client, testdata):
        # Test tagged
        ifname = testdata['interface_update']
        data = {
            "interfaces": {ifname: {"data": {"tagged_vlan_list": testdata['tagged_vlan_list']}}}
        }
        result = client.put(
            "/api/v1.0/device/{}/interfaces".format(testdata['interface_device']), json=data
        )
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        #        self.assertEqual(ifname in result.json['data']['updated'], True)
        # Test invalid
        data['interfaces'][ifname]['data']['tagged_vlan_list'] = ["thisshouldnetexist"]
        result = client.put(
            "/api/v1.0/device/{}/interfaces".format(testdata['interface_device']), json=data
        )
        assert result.status_code == 400
        assert result.json['status'] == 'error'

    def test_update_interface_data_description(self, client, testdata):
        # Reset descr
        ifname = testdata['interface_update']
        data = {"interfaces": {ifname: {"data": {"description": None}}}}
        result = client.put(
            "/api/v1.0/device/{}/interfaces".format(testdata['interface_device']), json=data
        )
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        # Update descr
        data['interfaces'][ifname]['data']['description'] = "Test update description"
        result = client.put(
            "/api/v1.0/device/{}/interfaces".format(testdata['interface_device']), json=data
        )
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        assert ifname in result.json['data']['updated']

    def test_update_interface_data_enabled(self, client, testdata):
        # Disable interface
        ifname = testdata['interface_update']
        data = {"interfaces": {ifname: {"data": {"enabled": False}}}}
        result = client.put(
            "/api/v1.0/device/{}/interfaces".format(testdata['interface_device']), json=data
        )
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        # Enable interface
        data['interfaces'][ifname]['data']['enabled'] = True
        result = client.put(
            "/api/v1.0/device/{}/interfaces".format(testdata['interface_device']), json=data
        )
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        assert ifname in result.json['data']['updated']

    def test_update_interface_data_neighbor(self, client, testdata):
        ifname = testdata['interface_update']
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
        result = client.put(
            "/api/v1.0/device/{}/interfaces".format(testdata['interface_device']),
            json=data
        )
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        assert ifname in result.json['data']['updated']
        # Reset
        data['interfaces'][ifname]['data']['neighbor_id'] = None
        data['interfaces'][ifname]['data']['neighbor'] = None
        result = client.put(
            "/api/v1.0/device/{}/interfaces".format(testdata['interface_device']),
            json=data
        )
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        assert ifname in result.json['data']['updated']

    def test_add_new_device(self, client):
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

    def test_get_joblocks(self, client):
        result = client.get('/api/v1.0/joblocks')

        # 200 OK
        assert result.status_code == 200
        # Success in json
        assert result.json['status'] == 'success'
        # Exactly one result
        # self.assertEqual(len(result.json['data']['jobs']), 1)

    @pytest.mark.equipment
    def test_get_interface_status(self, client, testdata):
        result = client.get(
            "/api/v1.0/device/{}/interface_status".format(testdata['interface_device'])
        )
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        assert 'interface_status' in result.json['data']

    @pytest.mark.equipment
    def test_bounce_interface(self, client, testdata):
        # Bounce of uplink should give error 400
        data = {'bounce_interfaces': [testdata['interface_uplink']]}
        result = client.put(
            "/api/v1.0/device/{}/interface_status".format(testdata['interface_device']), json=data
        )
        assert result.status_code == 400
        assert result.json['status'] == 'error'
        # Bounce of non-existing interface should give error 400
        data = {'bounce_interfaces': ['Ethernet999']}
        result = client.put(
            "/api/v1.0/device/{}/interface_status".format(testdata['interface_device']), json=data
        )
        assert result.status_code == 400
        assert result.json['status'] == 'error'
        # Try to bounce client interface
        data = {'bounce_interfaces': [testdata['interface_update']]}
        result = client.put(
            "/api/v1.0/device/{}/interface_status".format(testdata['interface_device']), json=data
        )
        assert result.status_code == 200
        assert result.json['status'] == 'success'

    def test_get_groups(self, client, testdata):
        groupname = testdata['groupname']
        result = client.get("/api/v1.0/groups")
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        assert groupname in result.json['data']['groups'], f"Group '{groupname}' not found"
        assert (
            len(result.json['data']['groups'][groupname]) >= 1
        ), f"No devices found in group '{groupname}'"

    def test_get_groups_osversion(self, client, testdata):
        groupname = testdata['groupname']
        result = client.get(f"/api/v1.0/groups/{groupname}/os_version")
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        assert (
            len(result.json['data']['groups'][groupname]) >= 1
        ), f"No devices found in group '{groupname}' os_versions"

    def test_renew_cert_errors(self, client, testdata):
        # Test invalid hostname
        data = {"hostname": "...", "action": "RENEW"}
        result = client.post('/api/v1.0/device_cert', json=data)
        assert result.status_code == 400

        # Test invalid action
        data = {"hostname": testdata['managed_dist']}
        result = client.post('/api/v1.0/device_cert', json=data)
        assert result.status_code == 400
        assert "action" in result.json['message'], "Unexpected error message"

    def test_generate_only_vars(self, client, testdata, templates_directory):
        result = client.get(
            "/api/v1.0/device/{}/generate_config".format(testdata['interface_device'])
        )
        assert result.status_code == 200
        assert result.json['status'] == 'success'
        assert (
            result.json['data']['config']['available_variables']['hostname']
            == testdata['interface_device']
        ), "hostname variable not found in generate_only variables"

    def test_linknet(self, client):
        post_data = {
            "device_a": "eosdist1",
            "device_a_port": "Ethernet3",
            "device_b": "eosdist2",
            "device_b_port": "Ethernet3",
        }
        result = client.post('/api/v1.0/linknets', json=post_data)
        assert result.status_code == 201, "Bad status code on POST"
        assert result.json['status'] == 'success'
        assert isinstance(result.json['data']['id'], int)
        assert isinstance(result.json['data']['ipv4_network'], str)
        assert "/" in result.json['data']['ipv4_network']
        linknet_id: int = result.json['data']['id']

        result = client.get('/api/v1.0/linknet/{}'.format(linknet_id))
        assert result.status_code == 200, "Bad status code on GET"
        assert result.json['status'] == 'success'
        assert len(result.json['data']['linknets']) == 1
        assert isinstance(result.json['data']['linknets'][0]['id'], int)
        assert result.json['data']['linknets'][0]['id'] == linknet_id

        result = client.get('/api/v1.0/linknets')
        assert result.status_code == 200, "Bad status code on GET all linknets"
        assert result.json['status'] == 'success'
        assert (
            len(result.json['data']['linknets']) >= 1
        ), "Less than one linknet found on GET linknets"

        put_data = {
            "ipv4_network": "10.198.0.0/31",
            "device_a_ip": "10.198.0.0",
            "device_b_ip": "10.198.0.1",
        }
        result = client.put('/api/v1.0/linknet/{}'.format(linknet_id), json=put_data)
        assert result.status_code == 200, "Bad status code on PUT with OK data"
        assert "updated_linknet" in result.json['data']
        put_data['device_b_ip'] = "10.198.0.0"  # Bad data
        result = client.put('/api/v1.0/linknet/{}'.format(linknet_id), json=put_data)
        assert result.status_code == 400, "Bad status code on PUT with bad data"
        assert result.json['status'] == 'error'

        result = client.delete('/api/v1.0/linknet/{}'.format(linknet_id))
        assert result.status_code == 200, "Bad status code on DELETE"
        assert result.json['status'] == 'success'
        assert isinstance(result.json['data']['deleted_linknet']['id'], int)
        assert result.json['data']['deleted_linknet']['id'] == linknet_id


@pytest.fixture
def client(app, redis, postgresql, settings_directory):
    return app.test_client()


@pytest.fixture
def app(jwt_auth_token):
    the_app = cnaas_nms.api.app.app
    the_app.wsgi_app = TestAppWrapper(the_app.wsgi_app, jwt_auth_token)
    return the_app


@pytest.fixture
def jwt_auth_token(testdata):
    return testdata.get('jwt_auth_token')


@pytest.fixture
def testdata(scope="session"):
    data_dir = pkg_resources.resource_filename(__name__, 'data')
    with open(os.path.join(data_dir, 'testdata.yml'), 'r') as f_testdata:
        return yaml.safe_load(f_testdata)


if __name__ == '__main__':
    unittest.main()
