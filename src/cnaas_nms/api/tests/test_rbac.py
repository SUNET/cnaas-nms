import pytest

from cnaas_nms.db.permissions import RoleMappings, RolePermissions, Roles
from cnaas_nms.db.session import sqla_session


@pytest.fixture(autouse=True)
def cleanup_rbac_test_data():
    """
    Cleanup fixture that runs before and after each test.
    Removes any test data that might have been left from failed tests.
    This prevents duplicate key errors on subsequent test runs.
    """

    def clean():
        with sqla_session() as session:  # type: ignore
            # First, get all test roles to find their IDs
            test_roles = session.query(Roles).filter(Roles.name.like("test_%")).all()
            test_role_ids = [role.id for role in test_roles]

            # Step 1: Delete test role mappings (both by attribute_value AND by role_id)
            # This must be done FIRST because mappings have foreign keys to roles
            if test_role_ids:
                test_mappings = (
                    session.query(RoleMappings)
                    .filter(
                        (RoleMappings.attribute_value.in_(["test_user_123", "john.doe", "admin@example.com"]))
                        | (RoleMappings.role_id.in_(test_role_ids))
                    )
                    .all()
                )
                for mapping in test_mappings:
                    session.delete(mapping)
                session.flush()  # Ensure mappings are deleted before proceeding

            # Step 2: Delete test role permissions
            # This must be done SECOND because permissions have foreign keys to roles
            if test_role_ids:
                test_permissions = (
                    session.query(RolePermissions).filter(RolePermissions.role_id.in_(test_role_ids)).all()
                )
                for permission in test_permissions:
                    session.delete(permission)
                session.flush()  # Ensure permissions are deleted before proceeding

            # Step 3: Delete test roles
            # This must be done LAST because roles are referenced by mappings and permissions
            for role in test_roles:
                session.delete(role)

            session.commit()

    # Clean before test
    clean()

    # Run the test
    yield

    # Clean after test (even if test failed)
    clean()


def test_rbac_workflow(client):
    """Test complete RBAC workflow: create role, role_permission, role_mapping, then verify via GET"""

    # Step 1: Create a new role
    role_data = {"name": "test_admin", "description": "Test administrator role"}

    create_role_response = client.post("/api/v1.0/rbac/roles", json=role_data)
    assert create_role_response.status_code == 201, f"Failed to create role: {create_role_response.json}"
    assert create_role_response.json["status"] == "success"
    assert "data" in create_role_response.json

    created_role = create_role_response.json["data"]
    assert created_role["name"] == "test_admin"
    assert created_role["description"] == "Test administrator role"
    role_id = created_role["id"]
    assert isinstance(role_id, int)

    # Step 2: Verify role via GET
    get_roles_response = client.get("/api/v1.0/rbac/roles")
    assert get_roles_response.status_code == 200
    assert get_roles_response.json["status"] == "success"
    roles = get_roles_response.json["data"]
    assert any(role["id"] == role_id and role["name"] == "test_admin" for role in roles)

    # Step 3: Create a role permission
    permission_data = {
        "role_id": role_id,
        "methods": ["GET", "POST"],
        "endpoints": ["/api/v1.0/devices*", "/api/v1.0/jobs*"],
        "exclude_endpoints": [],
        "pages": ["devices", "jobs"],
        "rights": ["read", "write"],
    }

    create_permission_response = client.post("/api/v1.0/rbac/role_permissions", json=permission_data)
    assert create_permission_response.status_code == 201, (
        f"Failed to create permission: {create_permission_response.json}"
    )
    assert create_permission_response.json["status"] == "success"

    created_permission = create_permission_response.json["data"]
    assert created_permission["role_id"] == role_id
    assert created_permission["methods"] == ["GET", "POST"]
    assert created_permission["endpoints"] == ["/api/v1.0/devices*", "/api/v1.0/jobs*"]
    assert created_permission["pages"] == ["devices", "jobs"]
    assert created_permission["rights"] == ["read", "write"]
    permission_id = created_permission["id"]
    assert isinstance(permission_id, int)

    # Step 4: Verify role permission via GET
    get_permissions_response = client.get("/api/v1.0/rbac/role_permissions")
    assert get_permissions_response.status_code == 200
    assert get_permissions_response.json["status"] == "success"
    permissions = get_permissions_response.json["data"]
    assert any(perm["id"] == permission_id and perm["role_id"] == role_id for perm in permissions)

    # Step 5: Create a role mapping
    mapping_data = {"attribute_name": "username", "attribute_value": "test_user_123", "role_id": role_id}

    create_mapping_response = client.post("/api/v1.0/rbac/role_mappings", json=mapping_data)
    assert create_mapping_response.status_code == 201, f"Failed to create mapping: {create_mapping_response.json}"
    assert create_mapping_response.json["status"] == "success"

    created_mapping = create_mapping_response.json["data"]
    assert created_mapping["attribute_name"] == "username"
    assert created_mapping["attribute_value"] == "test_user_123"
    assert created_mapping["role_id"] == role_id
    mapping_id = created_mapping["id"]
    assert isinstance(mapping_id, int)

    # Step 6: Verify role mapping via GET
    get_mappings_response = client.get("/api/v1.0/rbac/role_mappings")
    assert get_mappings_response.status_code == 200
    assert get_mappings_response.json["status"] == "success"
    mappings = get_mappings_response.json["data"]
    assert any(
        mapping["id"] == mapping_id and mapping["attribute_value"] == "test_user_123" and mapping["role_id"] == role_id
        for mapping in mappings
    )

    # Step 7: Delete the role mapping
    delete_mapping_response = client.delete(f"/api/v1.0/rbac/role_mappings/{mapping_id}")
    assert delete_mapping_response.status_code == 200, f"Failed to delete mapping: {delete_mapping_response.json}"
    assert delete_mapping_response.json["status"] == "success"

    # Step 8: Verify mapping is deleted
    get_mappings_after_delete = client.get("/api/v1.0/rbac/role_mappings")
    assert get_mappings_after_delete.status_code == 200
    mappings_after = get_mappings_after_delete.json["data"]
    assert not any(mapping["id"] == mapping_id for mapping in mappings_after)

    # Step 9: Delete the role permission
    delete_permission_response = client.delete(f"/api/v1.0/rbac/role_permissions/{permission_id}")
    assert delete_permission_response.status_code == 200, (
        f"Failed to delete permission: {delete_permission_response.json}"
    )
    assert delete_permission_response.json["status"] == "success"

    # Step 10: Verify permission is deleted
    get_permissions_after_delete = client.get("/api/v1.0/rbac/role_permissions")
    assert get_permissions_after_delete.status_code == 200
    permissions_after = get_permissions_after_delete.json["data"]
    assert not any(perm["id"] == permission_id for perm in permissions_after)

    # Step 11: Delete the role
    delete_role_response = client.delete(f"/api/v1.0/rbac/roles/{role_id}")
    assert delete_role_response.status_code == 200, f"Failed to delete role: {delete_role_response.json}"
    assert delete_role_response.json["status"] == "success"

    # Step 12: Verify role is deleted
    get_roles_after_delete = client.get("/api/v1.0/rbac/roles")
    assert get_roles_after_delete.status_code == 200
    roles_after = get_roles_after_delete.json["data"]
    assert not any(role["id"] == role_id for role in roles_after)


def test_create_multiple_roles(client):
    """Test creating multiple roles with different configurations"""

    roles_to_create = [
        {"name": "test_viewer", "description": "Test viewer role"},
        {"name": "test_operator", "description": "Test operator role"},
        {"name": "test_superadmin", "description": "Test superadmin role"},
    ]

    created_role_ids = []

    for role_data in roles_to_create:
        response = client.post("/api/v1.0/rbac/roles", json=role_data)
        assert response.status_code == 201, f"Failed to create role {role_data['name']}: {response.json}"
        assert response.json["status"] == "success"
        created_role_ids.append(response.json["data"]["id"])

    # Verify all roles exist
    get_response = client.get("/api/v1.0/rbac/roles")
    assert get_response.status_code == 200
    roles = get_response.json["data"]

    for role_data in roles_to_create:
        assert any(role["name"] == role_data["name"] for role in roles)

    # Delete all created roles
    for role_id in created_role_ids:
        delete_response = client.delete(f"/api/v1.0/rbac/roles/{role_id}")
        assert delete_response.status_code == 200, f"Failed to delete role {role_id}: {delete_response.json}"
        assert delete_response.json["status"] == "success"

    # Verify all roles are deleted
    get_after_delete = client.get("/api/v1.0/rbac/roles")
    assert get_after_delete.status_code == 200
    roles_after = get_after_delete.json["data"]
    for role_id in created_role_ids:
        assert not any(role["id"] == role_id for role in roles_after)


def test_create_permission_with_excludes(client):
    """Test creating role permission with exclude_endpoints"""

    # First create a role
    role_data = {"name": "test_restricted_admin", "description": "Admin with restrictions"}
    create_role_response = client.post("/api/v1.0/rbac/roles", json=role_data)
    assert create_role_response.status_code == 201
    role_id = create_role_response.json["data"]["id"]

    # Create permission with excludes
    permission_data = {
        "role_id": role_id,
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "endpoints": ["/api/v1.0/*"],
        "exclude_endpoints": ["/system*", "/rbac*"],
        "pages": ["devices", "jobs", "settings"],
        "rights": ["read", "write"],
    }

    response = client.post("/api/v1.0/rbac/role_permissions", json=permission_data)
    assert response.status_code == 201, f"Failed to create permission with excludes: {response.json}"
    assert response.json["status"] == "success"

    created_permission = response.json["data"]
    assert created_permission["exclude_endpoints"] == ["/system*", "/rbac*"]
    permission_id = created_permission["id"]

    # Delete the permission
    delete_permission_response = client.delete(f"/api/v1.0/rbac/role_permissions/{permission_id}")
    assert delete_permission_response.status_code == 200, (
        f"Failed to delete permission: {delete_permission_response.json}"
    )
    assert delete_permission_response.json["status"] == "success"

    # Delete the role
    delete_role_response = client.delete(f"/api/v1.0/rbac/roles/{role_id}")
    assert delete_role_response.status_code == 200, f"Failed to delete role: {delete_role_response.json}"
    assert delete_role_response.json["status"] == "success"


def test_create_mappings_for_different_attributes(client):
    """Test creating role mappings for different attribute types"""

    # Create roles for testing
    role_data = {"name": "test_group_role", "description": "Role for group testing"}
    create_role_response = client.post("/api/v1.0/rbac/roles", json=role_data)
    assert create_role_response.status_code == 201
    role_id = create_role_response.json["data"]["id"]

    # Create mappings for different attributes
    mappings_to_create = [
        {"attribute_name": "username", "attribute_value": "john.doe", "role_id": role_id},
        {"attribute_name": "group", "attribute_value": "network_admins", "role_id": role_id},
        {"attribute_name": "email", "attribute_value": "admin@example.com", "role_id": role_id},
    ]

    created_mapping_ids = []

    for mapping_data in mappings_to_create:
        response = client.post("/api/v1.0/rbac/role_mappings", json=mapping_data)
        assert response.status_code == 201, f"Failed to create mapping: {response.json}"
        assert response.json["status"] == "success"
        created_mapping_ids.append(response.json["data"]["id"])

    # Verify all mappings exist
    get_response = client.get("/api/v1.0/rbac/role_mappings")
    assert get_response.status_code == 200
    mappings = get_response.json["data"]

    for mapping_data in mappings_to_create:
        assert any(
            mapping["attribute_name"] == mapping_data["attribute_name"]
            and mapping["attribute_value"] == mapping_data["attribute_value"]
            and mapping["role_id"] == role_id
            for mapping in mappings
        )

    # Delete all mappings
    for mapping_id in created_mapping_ids:
        delete_mapping_response = client.delete(f"/api/v1.0/rbac/role_mappings/{mapping_id}")
        assert delete_mapping_response.status_code == 200, (
            f"Failed to delete mapping {mapping_id}: {delete_mapping_response.json}"
        )
        assert delete_mapping_response.json["status"] == "success"

    # Verify all mappings are deleted
    get_mappings_after_delete = client.get("/api/v1.0/rbac/role_mappings")
    assert get_mappings_after_delete.status_code == 200
    mappings_after = get_mappings_after_delete.json["data"]
    for mapping_id in created_mapping_ids:
        assert not any(mapping["id"] == mapping_id for mapping in mappings_after)

    # Delete the role
    delete_role_response = client.delete(f"/api/v1.0/rbac/roles/{role_id}")
    assert delete_role_response.status_code == 200, f"Failed to delete role: {delete_role_response.json}"
    assert delete_role_response.json["status"] == "success"


def test_create_permission_readonly(client):
    """Test creating a read-only role permission"""

    # Create a role
    role_data = {"name": "test_readonly", "description": "Read-only role"}
    create_role_response = client.post("/api/v1.0/rbac/roles", json=role_data)
    assert create_role_response.status_code == 201
    role_id = create_role_response.json["data"]["id"]

    # Create read-only permission
    permission_data = {
        "role_id": role_id,
        "methods": ["GET"],
        "endpoints": ["/api/v1.0/*"],
        "exclude_endpoints": [],
        "pages": ["devices", "jobs", "dashboard"],
        "rights": ["read"],
    }

    response = client.post("/api/v1.0/rbac/role_permissions", json=permission_data)
    assert response.status_code == 201, f"Failed to create readonly permission: {response.json}"
    assert response.json["status"] == "success"

    created_permission = response.json["data"]
    assert created_permission["methods"] == ["GET"]
    assert created_permission["rights"] == ["read"]
    permission_id = created_permission["id"]

    # Delete the permission
    delete_permission_response = client.delete(f"/api/v1.0/rbac/role_permissions/{permission_id}")
    assert delete_permission_response.status_code == 200, (
        f"Failed to delete permission: {delete_permission_response.json}"
    )
    assert delete_permission_response.json["status"] == "success"

    # Delete the role
    delete_role_response = client.delete(f"/api/v1.0/rbac/roles/{role_id}")
    assert delete_role_response.status_code == 200, f"Failed to delete role: {delete_role_response.json}"
    assert delete_role_response.json["status"] == "success"


def test_get_rbac_roles(client):
    """Test getting all RBAC roles"""
    ret = client.get("/api/v1.0/rbac/roles")
    assert ret.status_code == 200
    assert ret.json["status"] == "success"
    assert "data" in ret.json
    assert isinstance(ret.json["data"], list)
