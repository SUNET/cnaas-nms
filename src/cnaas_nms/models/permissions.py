from typing import Any, Dict, Optional

from pydantic import BaseModel, field_validator, model_validator


class PemissionConfig(BaseModel):
    default_permissions: str
    user_info_db_attr: list[str] = ["sub", "username", "preferred_username", "email"]


class PermissionModel(BaseModel):
    methods: Optional[list[str]] = []
    endpoints: Optional[list[str]] = []
    exclude_endpoints: Optional[list[str]] = []
    pages: Optional[list[str]] = []
    rights: Optional[list[str]] = []

    @field_validator("methods")
    def validate_methods(cls, v):
        valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "*"}
        for method in v:
            if method not in valid_methods:
                raise ValueError(f"Invalid HTTP method: {method}")
        return v


class RoleModel(BaseModel):
    permissions: list[PermissionModel]


class PermissionsModel(BaseModel):
    config: Optional[PemissionConfig] = None
    group_mappings: Optional[Dict[str, Any]] = {}
    roles: Dict[str, RoleModel]

    @model_validator(mode="after")
    def check_if_default_permissions_role_exist(self) -> "PermissionsModel":
        if self.config and self.config.default_permissions:
            if self.config.default_permissions not in self.roles:
                raise ValueError("Default permission is not defined")
        return self

    @model_validator(mode="after")
    def check_if_roles_in_mappings_exist(self) -> "PermissionsModel":
        if self.group_mappings is None:
            return self
        for map_type in self.group_mappings:
            for group in self.group_mappings[map_type]:
                for role_name in self.group_mappings[map_type][group]:
                    if role_name not in self.roles:
                        raise ValueError(
                            "Role permission:"
                            + role_name
                            + " is not defined, but is request for "
                            + group
                            + " in "
                            + map_type
                        )
        return self
