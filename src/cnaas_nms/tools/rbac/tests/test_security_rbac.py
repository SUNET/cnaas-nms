import unittest

from cnaas_nms.tools.rbac.rbac import check_if_api_call_is_permitted, get_permissions_user
from authlib.oauth2.rfc6749.wrappers import HttpRequest
from cnaas_nms.version import __api_version__

class CheckRoleRBACTests(unittest.TestCase):
    prefix = "/api/{}".format(__api_version__)
    def test_user_is_allowed_api_call(self):
        request = HttpRequest("GET", self.prefix + "/uri/")
        permissions_of_user = {"role":{"allowed_api_methods": ["GET"], "allowed_api_calls" : ["/uri"]}}
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertEqual(is_allowed, True)
    
    def test_user_is_allowed_api_call_with_star(self):
        request = HttpRequest("GET", self.prefix  + "/uri/")
        permissions_of_user = {"role":{"allowed_api_methods": ["*"], "allowed_api_calls" : ["*"]}}
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertEqual(is_allowed, True)
    
    def test_user_is_allowed_api_call_with_regex(self):
        request = HttpRequest("GET", self.prefix + "/uri/test")
        permissions_of_user = {"role":{"allowed_api_methods": ["GET"], "allowed_api_calls" : ["/uri/.*"]}}
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertEqual(is_allowed, True)

    def test_user_is_allowed_api_call_in_2nd_role(self):
        request = HttpRequest("GET", self.prefix + "/uri")
        permissions_of_user = {"role":{"allowed_api_methods": ["GET"], "allowed_api_calls" : ["no"]}, "role2":{"allowed_api_methods": ["GET"], "allowed_api_calls" : ["*"]}}
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertEqual(is_allowed, True)
    
    def test_user_is_not_allowed_api_call(self):
        request = HttpRequest("POST", self.prefix + "/uri")
        permissions_of_user = {"role":{"allowed_api_methods": ["GET"], "allowed_api_calls" : ["*"]}}
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertEqual(is_allowed, False)

    def test_user_is_not_allowed_api_call_with_regex(self):
        request = HttpRequest("GET", self.prefix  + "/different/test")
        permissions_of_user = {"role":{"allowed_api_methods": ["GET"], "allowed_api_calls" : ["/uri/.*"]}}
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertEqual(is_allowed, False)

    def test_user_is_not_allowed_api_call_empty(self):
        request = HttpRequest("GET", self.prefix + "/different/test")
        permissions_of_user = {}
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertEqual(is_allowed, False)
    
    def test_user_is_not_allowed_api_call_in_2_roles(self):
        request = HttpRequest("POST", self.prefix + "/different/test")
        permissions_of_user = {"role":{"allowed_api_methods": ["*"], "allowed_api_calls" : ["no"]}, "role2":{"allowed_api_methods": ["GET"], "allowed_api_calls" : ["*"]}}
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertEqual(is_allowed, False)

class GetPremissionsRoleYamlTests(unittest.TestCase):

    def test_role_permissions_with_default(self):
        permissions_rules = {'config': {'role_in_jwt_element': 'edumember_is_member_of', 'roles_separated_by': ':', 'default_permissions': 'any'}, 'roles': {'read': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs', '*']}, 'write': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['*']}, 'admin': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['/devices', '/jobs', '/repository/y.*']}, 'any': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs']}}}
        user_info = {"edumember_is_member_of":"read:write"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = {'write': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['*']}, 'read': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs', '*']}, 'any': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs']}}
        self.assertEqual(permissions_of_user, expected_result)

    def test_role_permissions(self):
        permissions_rules = {'config': {'role_in_jwt_element': 'edumember_is_member_of', 'roles_separated_by': ':'}, 'roles': {'read': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs', '*']}, 'write': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['*']}, 'admin': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['/devices', '/jobs', '/repository/y.*']}, 'any': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs']}}}
        user_info = {"edumember_is_member_of":"read:write"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = {'write': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['*']}, 'read': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs', '*']}}
        self.assertEqual(permissions_of_user, expected_result)

    def test_role_permissions_only_default(self):
        permissions_rules = {'config': {'role_in_jwt_element': 'edumember_is_member_of', 'roles_separated_by': ':', 'default_permissions': 'any'}, 'roles': {'read': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs', '*']}, 'write': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['*']}, 'admin': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['/devices', '/jobs', '/repository/y.*']}, 'any': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs']}}}
        user_info = {"edumember_is_member_of":"test:test2"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = {'any': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs']}}
        self.assertEqual(permissions_of_user, expected_result)

    def test_role_permissions_zero(self):
        permissions_rules = {'config': {'role_in_jwt_element': 'edumember_is_member_of', 'roles_separated_by': ':'}, 'roles': {'read': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs', '*']}, 'write': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['*']}, 'admin': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['/devices', '/jobs', '/repository/y.*']}, 'any': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs']}}}
        user_info = {"edumember_is_member_of":"test"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = {}
        self.assertEqual(permissions_of_user, expected_result)

    def test_role_permissions_default_expected_not_defined(self):
        permissions_rules = {'config': {'role_in_jwt_element': 'edumember_is_member_of', 'roles_separated_by': ':', 'default_permissions': 'any'}, 'roles': {'read': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs', '*']}, 'write': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['*']}, 'admin': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['/devices', '/jobs', '/repository/y.*']}}}
        user_info = {"edumember_is_member_of":"test"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = {}
        self.assertEqual(permissions_of_user, expected_result)

    def test_user_no_element_default(self):
        permissions_rules = {'config': {'role_in_jwt_element': 'edumember_is_member_of', 'roles_separated_by': ':', 'default_permissions': 'any'}, 'roles': {'read': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs', '*']}, 'write': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['*']}, 'admin': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['/devices', '/jobs', '/repository/y.*']}, 'any': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs']}}}
        user_info = {}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = {'any': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs']}}
        self.assertEqual(permissions_of_user, expected_result)
    
    def test_user_no_element_zero(self):
        permissions_rules = {'config': {'role_in_jwt_element': 'edumember_is_member_of', 'roles_separated_by': ':'}, 'roles': {'read': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs', '*']}, 'write': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['*']}, 'allowed_api_calls': ['/devices', '/jobs', '/repository/y.*']}, 'any': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs']}}
        user_info = {}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = {}
        self.assertEqual(permissions_of_user, expected_result)

    def test_rules_no_element_default(self):
        permissions_rules = {'config': {'roles_separated_by': ':', 'default_permissions': 'any'}, 'roles': {'read': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs', '*']}, 'write': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['*']}, 'admin': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['/devices', '/jobs', '/repository/y.*']}, 'any': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs']}}}
        user_info = {"edumember_is_member_of":"test"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = {'any': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs']}}
        self.assertEqual(permissions_of_user, expected_result)
    
    def test_rules_no_element_zero(self):
        permissions_rules = {'config': {'roles_separated_by': ':'}, 'roles': {'read': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs', '*']}, 'write': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['*']}, 'allowed_api_calls': ['/devices', '/jobs', '/repository/y.*']}, 'any': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs']}}
        user_info = {"edumember_is_member_of":"test"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = {}
        self.assertEqual(permissions_of_user, expected_result)

    def test_rules_empty(self):
        permissions_rules = {}
        user_info = {"edumember_is_member_of":"test"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = {}
        self.assertEqual(permissions_of_user, expected_result)
   
    def test_role_permissions_list(self):
        permissions_rules = {'config': {'role_in_jwt_element': 'edumember_is_member_of', 'roles_separated_by': ','}, 'roles': {'read': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs', '*']}, 'write': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['*']}, 'admin': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['/devices', '/jobs', '/repository/y.*']}, 'any': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs']}}}
        user_info = {"edumember_is_member_of":["read,write", "admin"]}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = {'write': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['*']}, 'read': {'allowed_api_methods': ['GET'], 'allowed_api_calls': ['/devices', '/jobs', '*']}, 'admin': {'allowed_api_methods': ['GET', 'PUT'], 'allowed_api_calls': ['/devices', '/jobs', '/repository/y.*']}}
        self.assertEqual(permissions_of_user, expected_result)

if __name__ == "__main__":
    unittest.main()
