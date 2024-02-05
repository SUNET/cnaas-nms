from typing import Dict, Optional

from pydantic import BaseModel, model_validator


class PemissionConfig(BaseModel):
    default_permissions: str


class PermissionModel(BaseModel):
    methods: Optional[list[str]] = []
    endpoints: Optional[list[str]] = []
    pages: Optional[list[str]] = []
    rights: Optional[list[str]] = []


class RoleModel(BaseModel):
    permissions: list[PermissionModel]


class PermissionsModel(BaseModel):
    config: Optional[PemissionConfig] = None
    group_mappings: Optional[Dict[str, Dict[str, list[str]]]] = {}
    roles: Dict[str, RoleModel]

    @model_validator(mode="after")
    def check_if_default_permissions_role_exist(self) -> "PermissionsModel":
        if self.config and self.config.default_permissions:
            if self.config.default_permissions not in self.roles:
                raise ValueError("Default permission is not defined")
        return self

    @model_validator(mode="after")
    def check_if_roles_in_mappings_exist(self) -> "PermissionsModel":
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

    # @model_validator(mode="after")
    # def check_default_or_mapping_defined(self) -> "PermissionsModel":
    #     if not self.group_mappings and (not self.config or not self.config.default_permissions):
    #         raise ValueError("Default permission and mappings are not defined. ")
    #     return self

  