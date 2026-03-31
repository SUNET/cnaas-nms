import zlib

import psycopg2.errors
from flask_restx import Namespace, Resource, fields
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from cnaas_nms.api.generic import empty_result
from cnaas_nms.app_settings import auth_settings
from cnaas_nms.db.permissions import RoleMappings, RolePermissions, Roles
from cnaas_nms.db.session import sqla_session
from cnaas_nms.models.permissions import PermissionModel
from cnaas_nms.tools.security import get_identity, login_required
from cnaas_nms.version import __api_version__

rbac_api = Namespace("rbac", description="RBAC related operations", prefix="/api/{}".format(__api_version__))

role_model = rbac_api.model(
    "Role",
    {
        "id": fields.Integer(readonly=True, description="The unique identifier of a role"),
        "name": fields.String(required=True, description="Role name"),
        "description": fields.String(description="Role description"),
    },
)

role_model_cud_model = rbac_api.model(
    "RoleCreateUpdate",
    {
        "status": fields.String(description="Status of the response"),
        "data": fields.Nested(role_model, description="Role data"),
    },
)

role_model_list_model = rbac_api.model(
    "RoleList",
    {
        "status": fields.String(description="Status of the response"),
        "data": fields.List(fields.Nested(role_model), description="List of roles"),
    },
)


class ApiError(Exception):
    def __init__(self, data: str, status_code: int = 400):
        super().__init__(data)
        self.status_code = status_code


def hash_to_32bit(s: str) -> int:
    """Hash role names to 32bit integer for use from permissions.yml"""
    return zlib.crc32(s.encode()) & 0xFFFFFFFF


class RoleApi(Resource):
    @rbac_api.marshal_with(role_model_list_model)
    @login_required
    def get(self):
        """Get a list of all roles"""
        ret = []
        # read roles from permissios.yml and add to the list
        if auth_settings.PERMISSIONS:
            permissions: PermissionModel = auth_settings.PERMISSIONS

            for role_name, role_data in permissions.roles.items():
                ret.append({"id": hash_to_32bit(role_name), "name": role_name, "description": "from permissions.yml"})
        with sqla_session() as session:  # type: ignore
            roles = session.query(Roles).all()
            for role in roles:
                ret.append(role.as_dict())
        return empty_result(status="success", data=ret)

    @rbac_api.expect(role_model, validate=True)
    @rbac_api.marshal_with(role_model_cud_model, code=201)
    @login_required
    def post(self):
        """Create a new role"""
        new_role = Roles(**rbac_api.payload)

        with sqla_session() as session:  # type: ignore
            session.add(new_role)
            session.commit()
            return empty_result(status="success", data=new_role.as_dict()), 201


class RoleApiById(Resource):
    @rbac_api.marshal_with(role_model_cud_model, code=200)
    @login_required
    def delete(self, role_id: int):
        """Delete a role by ID"""
        with sqla_session() as session:  # type: ignore
            role = session.query(Roles).filter(Roles.id == role_id).one_or_none()
            if role is None:
                raise ApiError(data=f"Role with id {role_id} does not exist", status_code=400)

            session.delete(role)
            session.commit()
            return empty_result(status="success", data=f"Role with id {role_id} deleted"), 200


role_mapping_model = rbac_api.model(
    "RoleMapping",
    {
        "id": fields.Integer(readonly=True, description="The unique identifier of a role mapping"),
        "attribute_name": fields.String(required=True, description="Attribute name"),
        "attribute_value": fields.String(required=True, description="Attribute value"),
        "role_id": fields.Integer(required=True, description="Role ID"),
        "last_modified_by": fields.String(readonly=True, description="Last modified by"),
        "last_modified": fields.DateTime(readonly=True, description="Last modified timestamp"),
    },
)

role_mapping_model_cud_model = rbac_api.model(
    "RoleMappingCreateUpdate",
    {
        "status": fields.String(description="Status of the response"),
        "data": fields.Nested(role_mapping_model, description="Role mapping data"),
    },
)

role_mapping_list_model = rbac_api.model(
    "RoleMappingList",
    {
        "status": fields.String(description="Status of the response"),
        "data": fields.List(fields.Nested(role_mapping_model), description="List of role mappings"),
    },
)


class RoleMappingApi(Resource):
    @rbac_api.marshal_with(role_mapping_list_model)
    @login_required
    def get(self):
        """Get a list of all role mappings"""
        ret = []
        if auth_settings.PERMISSIONS:
            permissions: PermissionModel = auth_settings.PERMISSIONS

            if permissions.group_mappings:
                for map_type, mappings in permissions.group_mappings.items():
                    for value, groups in mappings.items():
                        for group in groups:
                            ret.append(
                                {
                                    "id": None,
                                    "attribute_name": map_type,
                                    "attribute_value": value,
                                    "role_id": hash_to_32bit(group),
                                    "last_modified_by": "from permissions.yml",
                                    "last_modified": None,
                                }
                            )
        with sqla_session() as session:  # type: ignore
            mappings = session.query(RoleMappings).all()
            for mapping in mappings:
                ret.append(mapping.as_dict())
        return empty_result(status="success", data=ret)

    @rbac_api.expect(role_mapping_model, validate=True)
    @rbac_api.marshal_with(role_mapping_model_cud_model, code=201)
    @login_required
    def post(self):
        """Create a new role mapping"""
        new_mapping = RoleMappings(**rbac_api.payload, last_modified_by=get_identity())

        with sqla_session() as session:  # type: ignore
            session.add(new_mapping)
            session.commit()
            return empty_result(status="success", data=new_mapping.as_dict()), 201


class RoleMappingByIdApi(Resource):
    @rbac_api.marshal_with(role_model_cud_model, code=200)
    @login_required
    def delete(self, mapping_id: int):
        """Delete a role mapping by ID"""
        with sqla_session() as session:  # type: ignore
            mapping = session.query(RoleMappings).filter(RoleMappings.id == mapping_id).one_or_none()
            if mapping is None:
                raise ApiError(data=f"RoleMapping with id {mapping_id} does not exist", status_code=400)

            session.delete(mapping)
            session.commit()
            return empty_result(status="success", data=f"RoleMapping with id {mapping_id} deleted"), 200


role_permission_model = rbac_api.model(
    "RolePermission",
    {
        "id": fields.Integer(readonly=True, description="The unique identifier of a role permission"),
        "role_id": fields.Integer(required=True, description="Role ID"),
        "methods": fields.List(fields.String, required=True, description="List of HTTP methods"),
        "endpoints": fields.List(fields.String, required=True, description="List of API endpoints"),
        "exclude_endpoints": fields.List(fields.String, description="List of excluded API endpoints"),
        "pages": fields.List(fields.String, description="List of WebUI pages (devices, jobs, etc.)"),
        "rights": fields.List(fields.String, description="List of WebUI rights (read, write)"),
        "last_modified_by": fields.String(readonly=True, description="Last modified by"),
        "last_modified": fields.DateTime(readonly=True, description="Last modified timestamp"),
    },
)

role_permission_cud_model = rbac_api.model(
    "RolePermissionCreateUpdate",
    {
        "status": fields.String(description="Status of the response"),
        "data": fields.Nested(role_permission_model, description="Role permission data"),
    },
)

role_permission_list_model = rbac_api.model(
    "RolePermissionList",
    {
        "status": fields.String(description="Status of the response"),
        "data": fields.List(fields.Nested(role_permission_model), description="List of role permissions"),
    },
)


class RolePermissionApi(Resource):
    @rbac_api.marshal_with(role_permission_list_model)
    @login_required
    def get(self):
        """Get a list of all role permissions"""
        ret = []
        if auth_settings.PERMISSIONS:
            permissions: PermissionModel = auth_settings.PERMISSIONS

            for role_name, role_data in permissions.roles.items():
                for permission in role_data.permissions:
                    ret.append(
                        {
                            "id": None,
                            "role_id": hash_to_32bit(role_name),
                            "methods": permission.methods if permission else [],
                            "endpoints": permission.endpoints if permission else [],
                            "exclude_endpoints": permission.exclude_endpoints if permission else [],
                            "pages": permission.pages if permission else [],
                            "rights": permission.rights if permission else [],
                            "last_modified_by": "from permissions.yml",
                            "last_modified": None,
                        }
                    )
        with sqla_session() as session:  # type: ignore
            permissions = session.query(RolePermissions).all()
            for permission in permissions:
                ret.append(permission.as_dict())
        return empty_result(status="success", data=ret)

    @rbac_api.expect(role_permission_model, validate=True)
    @rbac_api.marshal_with(role_permission_cud_model, code=201)
    @login_required
    def post(self):
        """Create a new role permission"""
        new_permission = RolePermissions(**rbac_api.payload, last_modified_by=get_identity())

        # pydantic model validation
        PermissionModel(**new_permission.as_dict()).model_dump()

        with sqla_session() as session:  # type: ignore
            role = session.query(Roles).filter(Roles.id == new_permission.role_id).one_or_none()
            if role is None:
                raise ApiError(data=f"Role with id {new_permission.role_id} does not exist", status_code=400)

            session.add(new_permission)
            session.commit()
            return empty_result(status="success", data=new_permission.as_dict()), 201


class RolePermissionByIdApi(Resource):
    @rbac_api.expect(role_permission_model, validate=True)
    @rbac_api.marshal_with(role_permission_cud_model)
    @login_required
    def put(self, permission_id: int):
        """Update an existing role permission"""
        updated_permission = RolePermissions(**rbac_api.payload)

        # pydantic model validation
        PermissionModel(**updated_permission.as_dict()).model_dump()

        with sqla_session() as session:  # type: ignore
            existing_permission = (
                session.query(RolePermissions).filter(RolePermissions.id == permission_id).one_or_none()
            )
            if existing_permission is None:
                raise ApiError(data=f"RolePermission with id {permission_id} does not exist", status_code=400)

            role = session.query(Roles).filter(Roles.id == updated_permission.role_id).one_or_none()
            if role is None:
                raise ApiError(data=f"Role with id {updated_permission.role_id} does not exist", status_code=400)

            for field in ["role_id", "methods", "endpoints", "exclude_endpoints", "pages", "rights"]:
                if getattr(updated_permission, field) is not None:
                    setattr(existing_permission, field, getattr(updated_permission, field))

            existing_permission.last_modified_by = str(get_identity())

            session.commit()
            return empty_result(status="success", data=existing_permission.as_dict()), 200

    @rbac_api.marshal_with(role_permission_cud_model, code=200)
    @login_required
    def delete(self, permission_id: int):
        """Delete a role permission by ID"""
        with sqla_session() as session:  # type: ignore
            permission = session.query(RolePermissions).filter(RolePermissions.id == permission_id).one_or_none()
            if permission is None:
                raise ApiError(data=f"RolePermission with id {permission_id} does not exist", status_code=400)

            session.delete(permission)
            session.commit()
            return empty_result(status="success", data=f"RolePermission with id {permission_id} deleted"), 200


@rbac_api.errorhandler(IntegrityError)
def handle_integrity_error(e):
    if e.orig and isinstance(e.orig, psycopg2.errors.UniqueViolation):
        return empty_result(status="error", data=f"Entry is not unique: {str(e)}"), 400
    elif e.orig and isinstance(e.orig, psycopg2.errors.ForeignKeyViolation):
        return empty_result(status="error", data=f"Relation error: {str(e)}"), 400
    return empty_result(status="error", data=f"Integrity error: {str(e)}"), 500


@rbac_api.errorhandler(ApiError)
def handle_api_error(error):
    return empty_result(status="error", data=f"Error: {str(error)}"), error.status_code


@rbac_api.errorhandler(ValidationError)
def handle_validation_error(error):
    return empty_result(status="error", data=f"Validation Error: {str(error)}"), 400


@rbac_api.errorhandler
def handle_exception(error):
    return empty_result(status="error", data=f"Generic Error: {str(error)}"), 400


rbac_api.add_resource(RoleApi, "/roles")
rbac_api.add_resource(RoleApiById, "/roles/<int:role_id>")
rbac_api.add_resource(RoleMappingApi, "/role_mappings")
rbac_api.add_resource(RoleMappingByIdApi, "/role_mappings/<int:mapping_id>")
rbac_api.add_resource(RolePermissionApi, "/role_permissions")
rbac_api.add_resource(RolePermissionByIdApi, "/role_permissions/<int:permission_id>")
