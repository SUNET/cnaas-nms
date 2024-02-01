from typing import Dict, Optional
from pydantic import BaseModel, validator, model_validator

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
    group_mappings: Optional[Dict[str, Dict[str, list[str]]] ] = {}
    roles: Dict[str, RoleModel] 



    @model_validator(mode='after')
    def check_if_default_permissions_role_exist(self) -> 'PermissionsModel':
        if self.config and self.config.default_permissions:
            if self.config.default_permissions not in self.roles:
                raise ValueError("Default permission is not defined")
        return self
    
    @model_validator(mode='after')
    def check_if_roles_in_mappings_exist(self) -> 'PermissionsModel':
        for group_mapping in self.group_mappings:
            for group in self.group_mappings[group_mapping]:
                for role_name in self.group_mappings[group_mapping][group]:
                    if role_name not in self.roles:
                        raise ValueError("Role permission:" + role_name + " is not defined, but is request for " + group + " in " + group_mapping)
        return self