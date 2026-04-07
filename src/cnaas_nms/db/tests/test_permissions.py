import pytest
from authlib.oauth2 import JsonRequest

from cnaas_nms.db.permissions import (
    RoleMappings,
    RolePermissions,
    Roles,
    combine_permissions,
    get_all_user_db_permissions,
)
from cnaas_nms.db.session import sqla_session
from cnaas_nms.models.permissions import PermissionModel
from cnaas_nms.tools.rbac.rbac import check_if_api_call_is_permitted
from cnaas_nms.version import __api_version__

pytestmark = pytest.mark.integration

prefix = "/api/{}".format(__api_version__)


def test_combine_permissions_with_data(postgresql):
    """Test combine_permissions with populated tables"""
    with sqla_session() as session:  # type: ignore
        # Setup test data
        role = Roles(name="admin")

        session.add(role)
        session.flush()

        user_role = RoleMappings(attribute_name="username", attribute_value="testuser", role_id=role.id)
        role_permission = RolePermissions(
            role_id=role.id, methods=["GET"], endpoints=["/devices"], pages=["dashboard"], rights=["read", "write"]
        )

        session.add(user_role)
        session.add(role_permission)
        user_info = {"username": "testuser"}
        db_permissions = get_all_user_db_permissions(session, user_info, ["username"])

        file_permissions = [PermissionModel(methods=["GET", "POST"], endpoints=["/auth/*"])]
        combined_permissions = combine_permissions(db_permissions, file_permissions)
        session.rollback()

        request_fail = JsonRequest("GET", prefix + "/uri/test")
        is_allowed = check_if_api_call_is_permitted(request_fail, combined_permissions)
        assert is_allowed is False

        request_ok = JsonRequest("GET", prefix + "/devices")
        is_allowed = check_if_api_call_is_permitted(request_ok, combined_permissions)
        assert is_allowed is True

        request_ok = JsonRequest("GET", prefix + "/auth/test")
        is_allowed = check_if_api_call_is_permitted(request_ok, combined_permissions)
        assert is_allowed is True
