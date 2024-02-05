import unittest

from authlib.oauth2.rfc6749.requests import JsonRequest

from cnaas_nms.models.permissions import PemissionConfig, PermissionModel, PermissionsModel, RoleModel
from cnaas_nms.tools.rbac.rbac import check_if_api_call_is_permitted, get_permissions_user
from cnaas_nms.version import __api_version__


class CheckRoleRBACTests(unittest.TestCase):
    prefix = "/api/{}".format(__api_version__)

    def test_user_is_allowed_api_call(self):
        request = JsonRequest("GET", self.prefix + "/devices")
        permissions_of_user = [PermissionModel(methods=["GET", "POST"], endpoints=["/auth/*", "/devices"])]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertTrue(is_allowed)

    def test_user_is_allowed_api_call_with_star(self):
        request = JsonRequest("GET", self.prefix + "/uri")
        permissions_of_user = [PermissionModel(methods=["*"], endpoints=["*"])]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertTrue(is_allowed)

    def test_user_is_allowed_api_call_with_glob(self):
        request = JsonRequest("GET", self.prefix + "/uri/test")
        permissions_of_user = [PermissionModel(methods=["GET"], endpoints=["/uri/*"])]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertTrue(is_allowed)

    def test_user_is_allowed_api_call_with_glob_double_star(self):
        request = JsonRequest("GET", self.prefix + "/uri/test/test")
        permissions_of_user = [PermissionModel(methods=["GET"], endpoints=["/uri/**"])]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertTrue(is_allowed)

    def test_user_is_allowed_api_call_multiple_permissions(self):
        request = JsonRequest("GET", self.prefix + "/uri")
        permissions_of_user = [
            PermissionModel(methods=["GET"], endpoints=["no"]),
            PermissionModel(methods=["GET"], endpoints=["*"]),
        ]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertTrue(is_allowed)

    def test_user_is_not_allowed_api_call_method(self):
        request = JsonRequest("POST", self.prefix + "/uri")
        permissions_of_user = [PermissionModel(methods=["GET"], endpoints=["*"])]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertFalse(is_allowed)

    def test_user_is_not_allowed_api_call_with_glob(self):
        request = JsonRequest("GET", self.prefix + "/different/test")
        permissions_of_user = [PermissionModel(methods=["GET"], endpoints=["/uri/**"])]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertFalse(is_allowed)

    def test_user_is_not_allowed_api_call_empty(self):
        request = JsonRequest("GET", self.prefix + "/different/test")
        permissions_of_user = []
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertFalse(is_allowed)

    def test_user_is_not_allowed_api_call_in_2_roles(self):
        request = JsonRequest("POST", self.prefix + "/different/test/test")
        permissions_of_user = [
            PermissionModel(methods=["*"], endpoints=["/uri/*"]),
            PermissionModel(methods=["GET"], endpoints=["*"]),
        ]
        is_allowed = check_if_api_call_is_permitted(request, permissions_of_user)
        self.assertFalse(is_allowed)


class GetPremissionsRoleYamlTests(unittest.TestCase):
    def test_role_permissions_with_default(self):
        permissions_rules = PermissionsModel(
            config=PemissionConfig(default_permissions="default"),
            group_mappings={
                "edumember_is_member_of": {
                    "urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin": ["admin"]
                }
            },
            roles={
                "admin": RoleModel(
                    permissions=[
                        PermissionModel(methods=["GET", "PUT"], endpoints=["/devices/**/interfaces", "/repository"]),
                        PermissionModel(methods=["POST"], endpoints=["/auth/*", "/devices"]),
                    ]
                ),
                "default": RoleModel(permissions=[PermissionModel(methods=["GET"], endpoints=["/devices**"])]),
            },
        )
        user_info = {
            "edumember_is_member_of": "urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin"
        }
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = [
            PermissionModel(methods=["GET"], endpoints=["/devices**"]),
            PermissionModel(methods=["GET", "PUT"], endpoints=["/devices/**/interfaces", "/repository"]),
            PermissionModel(methods=["POST"], endpoints=["/auth/*", "/devices"]),
        ]
        self.assertEqual(permissions_of_user, expected_result)

    def test_role_permissions(self):
        permissions_rules = PermissionsModel(
            group_mappings={
                "edumember_is_member_of": {
                    "urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin": ["admin"]
                }
            },
            roles={
                "admin": RoleModel(
                    permissions=[
                        PermissionModel(methods=["GET", "PUT"], endpoints=["/devices/**/interfaces", "/repository"]),
                        PermissionModel(methods=["POST"], endpoints=["/auth/*", "/devices"]),
                    ]
                )
            },
        )

        user_info = {
            "edumember_is_member_of": "urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin"
        }
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = [
            PermissionModel(methods=["GET", "PUT"], endpoints=["/devices/**/interfaces", "/repository"]),
            PermissionModel(methods=["POST"], endpoints=["/auth/*", "/devices"]),
        ]
        self.assertEqual(permissions_of_user, expected_result)

    def test_role_permissions_only_default(self):
        permissions_rules = PermissionsModel(
            config=PemissionConfig(default_permissions="default"),
            group_mappings={
                "edumember_is_member_of": {
                    "urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin": ["admin"]
                }
            },
            roles={
                "admin": RoleModel(
                    permissions=[
                        PermissionModel(methods=["GET", "PUT"], endpoints=["/devices/**/interfaces", "/repository"]),
                        PermissionModel(methods=["POST"], endpoints=["/auth/*", "/devices"]),
                    ]
                ),
                "default": RoleModel(permissions=[PermissionModel(methods=["GET"], endpoints=["/devices**"])]),
            },
        )
        user_info = {"edumember_is_member_of": "notarealrole"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = [PermissionModel(methods=["GET"], endpoints=["/devices**"])]
        self.assertEqual(permissions_of_user, expected_result)

    def test_role_permissions_zero(self):
        permissions_rules = PermissionsModel(
            group_mappings={
                "edumember_is_member_of": {
                    "urn:collab:group:test.surfconext.nl:nl:surfnet:diensten:surfwired-admin": ["admin"]
                }
            },
            roles={
                "admin": RoleModel(
                    permissions=[
                        PermissionModel(methods=["GET", "PUT"], endpoints=["/devices/**/interfaces", "/repository"]),
                        PermissionModel(methods=["POST"], endpoints=["/auth/*", "/devices"]),
                    ]
                ),
                "default": RoleModel(permissions=[PermissionModel(methods=["GET"], endpoints=["/devices**"])]),
            },
        )
        user_info = {"edumember_is_member_of": "notarealrole"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = []
        self.assertEqual(permissions_of_user, expected_result)

    def test_user_no_element_zero(self):
        permissions_rules = PermissionsModel(
            roles={
                "admin": RoleModel(
                    permissions=[
                        PermissionModel(methods=["GET", "PUT"], endpoints=["/devices/**/interfaces", "/repository"]),
                        PermissionModel(methods=["POST"], endpoints=["/auth/*", "/devices"]),
                    ]
                ),
                "default": RoleModel(permissions=[PermissionModel(methods=["GET"], endpoints=["/devices**"])]),
            }
        )
        user_info = {}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = []
        self.assertEqual(permissions_of_user, expected_result)

    def test_rules_empty(self):
        permissions_rules = {}
        user_info = {"edumember_is_member_of": "test"}
        permissions_of_user = get_permissions_user(permissions_rules, user_info)
        expected_result = []
        self.assertEqual(permissions_of_user, expected_result)


if __name__ == "__main__":
    unittest.main()
