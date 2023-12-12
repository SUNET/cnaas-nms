import unittest
import pathlib
import fnmatch
from pathlib import Path
from cnaas_nms.tools.rbac.rbac import check_if_api_call_is_permitted, get_permissions_user
from authlib.oauth2.rfc6749.wrappers import HttpRequest
from cnaas_nms.version import __api_version__

class CheckRoleRBACTests(unittest.TestCase):
    prefix = "/api/{}".format(__api_version__)
    def test_user_is_allowed_api_call(self):
        request = HttpRequest("GET", self.prefix + "/devices")
        permissions_of_user = [{'methods': ['GET' ,'POST'], 'endpoints': ['/auth/*', '/devices']}]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertTrue(is_allowed)
    
    def test_user_is_allowed_api_call_with_star(self):
        request = HttpRequest("GET", self.prefix  + "/uri")
        permissions_of_user = [{"methods": ["*"], "endpoints" : ["*"]}]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertTrue(is_allowed)
    
    def test_user_is_allowed_api_call_with_glob(self):
        request = HttpRequest("GET", self.prefix + "/uri/test")
        permissions_of_user = [{"methods": ["GET"], "endpoints" : ["/uri/*"]}]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertTrue(is_allowed)
    
    def test_user_is_allowed_api_call_with_glob_double_star(self):
        request = HttpRequest("GET", self.prefix + "/uri/test/test")
        permissions_of_user = [{"methods": ["GET"], "endpoints" : ["/uri/**"]}]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertTrue(is_allowed)

    def test_user_is_allowed_api_call_multiple_permissions(self):
        request = HttpRequest("GET", self.prefix + "/uri")
        permissions_of_user = [{"methods": ["GET"], "endpoints" : ["no"]}, {"methods": ["GET"], "endpoints" : ["*"]}]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertTrue(is_allowed)
    
    def test_user_is_not_allowed_api_call_method(self):
        request = HttpRequest("POST", self.prefix + "/uri")
        permissions_of_user = [{"methods": ["GET"], "endpoints" : ["*"]}]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertFalse(is_allowed)

    def test_user_is_not_allowed_api_call_with_glob(self):
        request = HttpRequest("GET", self.prefix  + "/different/test")
        permissions_of_user =[{"methods": ["GET"], "endpoints" : ["/uri/**"]}]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertFalse(is_allowed)

    def test_user_is_not_allowed_api_call_empty(self):
        request = HttpRequest("GET", self.prefix + "/different/test")
        permissions_of_user = []
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertFalse(is_allowed)
    
    def test_user_is_not_allowed_api_call_in_2_roles(self):
        request = HttpRequest("POST", self.prefix + "/different/test/test")
        permissions_of_user = [{"methods": ["*"], "endpoints" : ["/uri/*"]}, {"methods": ["GET"], "endpoints" : ["*"]}]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertFalse(is_allowed)

class GetPremissionsRoleYamlTests(unittest.TestCase):

    def test_role_permissions_with_default(self):
        permissions_rules = {'config': {'group_claim_key': 'edumember_is_member_of', 'default_permissions': 'default'}, 'roles': {'urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin': {'permissions': [{'methods': ['GET', 'PUT'], 'endpoints': ['/devices/**/interfaces', '/repository']}, {'methods': ['POST'], 'endpoints': ['/auth/*', '/devices']}]}, 'default': {'permissions': [{'methods': ['GET'], 'endpoints': ['/devices**']}]}}}
        user_info = {"edumember_is_member_of":"urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result =[{'methods': ['GET'], 'endpoints': ['/devices**']}, {'methods': ['GET', 'PUT'], 'endpoints': ['/devices/**/interfaces', '/repository']}, {'methods': ['POST'], 'endpoints': ['/auth/*', '/devices']}]
        self.assertEqual(permissions_of_user, expected_result)

    def test_role_permissions(self):
        permissions_rules = {'config': {'group_claim_key': 'edumember_is_member_of', 'default_permissions': 'default'}, 'roles': {'urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin': {'permissions': [{'methods': ['GET', 'PUT'], 'endpoints': ['/devices/**/interfaces', '/repository']}, {'methods': ['POST'], 'endpoints': ['/auth/*', '/devices']}]}}}
        user_info = {"edumember_is_member_of":"urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = [{'methods': ['GET', 'PUT'], 'endpoints': ['/devices/**/interfaces', '/repository']}, {'methods': ['POST'], 'endpoints': ['/auth/*', '/devices']}]
        self.assertEqual(permissions_of_user, expected_result)

    def test_role_permissions_only_default(self):
        permissions_rules = {'config': {'group_claim_key': 'edumember_is_member_of', 'default_permissions': 'default'}, 'roles': {'urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin': {'permissions': [{'methods': ['GET', 'PUT'], 'endpoints': ['/devices/**/interfaces', '/repository']}, {'methods': ['POST'], 'endpoints': ['/auth/*', '/devices']}]}, 'default': {'permissions': [{'methods': ['GET'], 'endpoints': ['/devices**']}]}}}
        user_info = {"edumember_is_member_of":"notarealrole"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = [{'methods': ['GET'], 'endpoints': ['/devices**']}]
        self.assertEqual(permissions_of_user, expected_result)

    def test_role_permissions_zero(self):
        permissions_rules = {'config': {'group_claim_key': 'edumember_is_member_of', 'default_permissions': 'default'}, 'roles': {'urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin': {'permissions': [{'methods': ['GET', 'PUT'], 'endpoints': ['/devices/**/interfaces', '/repository']}, {'methods': ['POST'], 'endpoints': ['/auth/*', '/devices']}]}}}
        user_info = {"edumember_is_member_of":"notarealrole"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = []
        self.assertEqual(permissions_of_user, expected_result)

    def test_user_no_element_default(self):
        permissions_rules = {'config': {'group_claim_key': 'edumember_is_member_of', 'default_permissions': 'default'}, 'roles': {'urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin': {'permissions': [{'methods': ['GET', 'PUT'], 'endpoints': ['/devices/**/interfaces', '/repository']}, {'methods': ['POST'], 'endpoints': ['/auth/*', '/devices']}]}, 'default': {'permissions': [{'methods': ['GET'], 'endpoints': ['/devices**']}]}}}
        user_info = {}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = [{'methods': ['GET'], 'endpoints': ['/devices**']}]
        self.assertEqual(permissions_of_user, expected_result)
    
    def test_user_no_element_zero(self):
        permissions_rules = {'config': {'group_claim_key': 'edumember_is_member_of'}, 'roles': {'urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin': {'permissions': [{'methods': ['GET', 'PUT'], 'endpoints': ['/devices/**/interfaces', '/repository']}, {'methods': ['POST'], 'endpoints': ['/auth/*', '/devices']}]}, 'default': {'permissions': [{'methods': ['GET'], 'endpoints': ['/devices**']}]}}}
        user_info = {}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = []
        self.assertEqual(permissions_of_user, expected_result)

    def test_rules_empty(self):
        permissions_rules = {}
        user_info = {"edumember_is_member_of":"test"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = []
        self.assertEqual(permissions_of_user, expected_result)
   
    def test_role_permissions_list(self):
        permissions_rules = {'config': {'group_claim_key': 'edumember_is_member_of', 'default_permissions': 'default'}, 'roles': {'urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin': {'permissions': [{'methods': ['GET', 'PUT'], 'endpoints': ['/devices/**/interfaces', '/repository']}, {'methods': ['POST'], 'endpoints': ['/auth/*', '/devices']}]}, 'default': {'permissions': [{'methods': ['GET'], 'endpoints': ['/devices**']}]}}}
        user_info = {"edumember_is_member_of":["test", "urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin"]}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result =[{'methods': ['GET'], 'endpoints': ['/devices**']}, {'methods': ['GET', 'PUT'], 'endpoints': ['/devices/**/interfaces', '/repository']}, {'methods': ['POST'], 'endpoints': ['/auth/*', '/devices']}]
        self.assertEqual(permissions_of_user, expected_result)

if __name__ == "__main__":
    unittest.main()
