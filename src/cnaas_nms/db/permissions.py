import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Unicode
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column

import cnaas_nms.db.base
from cnaas_nms.models.permissions import PermissionModel


class Roles(cnaas_nms.db.base.Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, autoincrement=True, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Unicode(1024), nullable=True)

    def as_dict(self) -> dict:
        """Return JSON serializable dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }


class RolePermissions(cnaas_nms.db.base.Base):
    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, primary_key=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"))
    description: Mapped[str] = mapped_column(Unicode(1024), nullable=True)
    methods = mapped_column(MutableList.as_mutable(JSONB), default=[])
    endpoints = mapped_column(MutableList.as_mutable(JSONB), default=[])
    exclude_endpoints = mapped_column(MutableList.as_mutable(JSONB), default=[])
    pages = mapped_column(MutableList.as_mutable(JSONB), default=[])
    rights = mapped_column(MutableList.as_mutable(JSONB), default=[])
    last_modified_by: Mapped[str] = mapped_column(Unicode(255), nullable=True)
    last_modified: Mapped[DateTime] = mapped_column(DateTime, default=datetime.datetime.now)

    __table_args__ = (Index("ix_role_permissions_role_id", "role_id"),)

    def as_dict(self) -> dict:
        """Return JSON serializable dict."""
        return {
            "id": self.id,
            "role_id": self.role_id,
            "description": self.description,
            "methods": self.methods,
            "endpoints": self.endpoints,
            "exclude_endpoints": self.exclude_endpoints,
            "pages": self.pages,
            "rights": self.rights,
            "last_modified_by": self.last_modified_by,
            "last_modified": self.last_modified,
        }


class RoleMappings(cnaas_nms.db.base.Base):
    __tablename__ = "role_mappings"
    id: Mapped[int] = mapped_column(Integer, autoincrement=True, primary_key=True)
    attribute_name: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    attribute_value: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"))
    last_modified_by: Mapped[str] = mapped_column(Unicode(255), nullable=True)
    last_modified: Mapped[DateTime] = mapped_column(DateTime, default=datetime.datetime.now)

    __table_args__ = (
        Index("ix_role_mappings_attribute", "attribute_name", "attribute_value"),
        Index("ix_role_mappings_role_id", "role_id"),
    )

    def as_dict(self) -> dict:
        """Return JSON serializable dict."""
        return {
            "id": self.id,
            "attribute_name": self.attribute_name,
            "attribute_value": self.attribute_value,
            "role_id": self.role_id,
            "last_modified_by": self.last_modified_by,
            "last_modified": self.last_modified,
        }


#
def get_all_user_db_permissions(
    session, user_info: dict, user_info_attributes_in_db: list[str]
) -> list[PermissionModel]:
    """Get all permissions for a user based on their roles"""
    if not user_info_attributes_in_db or not isinstance(user_info_attributes_in_db, list):
        return []

    permissions: list[PermissionModel] = []
    for attribute_name, attribute_value in user_info.items():
        if attribute_name not in user_info_attributes_in_db:
            continue
        user_roles = (
            session.query(RoleMappings)
            .filter(RoleMappings.attribute_name == attribute_name)
            .filter(RoleMappings.attribute_value == attribute_value)
            .all()
        )
        for user_role in user_roles:
            role_permissions = session.query(RolePermissions).filter(RolePermissions.role_id == user_role.role_id).all()
            for role_permission in role_permissions:
                perm_model = PermissionModel(
                    methods=role_permission.methods,
                    endpoints=role_permission.endpoints,
                    exclude_endpoints=role_permission.exclude_endpoints,
                    pages=role_permission.pages,
                    rights=role_permission.rights,
                )
                permissions.append(perm_model)
    return permissions


def combine_permissions(db_permissions: list[PermissionModel], file_permissions: list[PermissionModel]):
    """Combine permissions from database and file"""
    combined_permissions: list[PermissionModel] = []

    # Add database permissions
    for db_perm in db_permissions:
        combined_permissions.append(db_perm)

    # Add file permissions
    for file_perm in file_permissions:
        combined_permissions.append(file_perm)

    return combined_permissions
