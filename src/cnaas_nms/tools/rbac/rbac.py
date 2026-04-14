import fnmatch
from typing import List

from authlib.integrations.flask_oauth2.requests import FlaskJsonRequest

from cnaas_nms.db.permissions import get_all_user_db_permissions
from cnaas_nms.db.session import sqla_session
from cnaas_nms.models.permissions import PermissionModel, PermissionsModel
from cnaas_nms.version import __api_version__


def get_permissions_user(permissions_rules: PermissionsModel, user_info: dict):
    """Get the API permissions of the user"""
    permissions_of_user: list[PermissionModel] = []

    # if no rules, return
    if not permissions_rules:
        return permissions_of_user

    # first give all the permissions of the fallback role
    if permissions_rules.config and permissions_rules.config.default_permissions:
        default_role = permissions_rules.roles.get(permissions_rules.config.default_permissions)
        if default_role is not None:
            permissions_of_user.extend(default_role.permissions)

    user_roles: List[str] = []
    # read the group mappings and add the relevant roles
    if permissions_rules.group_mappings:
        map_type: str
        mappings: dict[str, list[str]]
        for map_type, mappings in permissions_rules.group_mappings.items():
            for value, groups in mappings.items():
                if map_type in user_info:
                    # if the type is a list in userinfo, we check if the value is in the list
                    # if not a list, we assume it's a string and compare it directly
                    if (isinstance(user_info[map_type], list) and value in user_info[map_type]) or value == user_info[
                        map_type
                    ]:
                        user_roles.extend(groups)

    # find the relevant roles and add permissions
    relevant_roles = list(set(permissions_rules.roles) & set(user_roles))
    for relevant_role in relevant_roles:
        permissions_of_user.extend(permissions_rules.roles[relevant_role].permissions)

    if permissions_rules.config and permissions_rules.config.user_info_db_attr:
        with sqla_session() as session:
            permissions_of_user.extend(
                get_all_user_db_permissions(session, user_info, permissions_rules.config.user_info_db_attr)
            )

    return permissions_of_user


def _uri_matches_any_pattern(uri: str, patterns: list[str]) -> bool:
    """Check if a URI matches any of the given fnmatch patterns."""
    if uri in patterns:
        return True
    for pattern in patterns:
        if fnmatch.filter([uri], pattern):
            return True
    return False


def check_if_api_call_is_permitted(request: FlaskJsonRequest, permissions_of_user: list[PermissionModel]):
    """Checks if the user has permission to execute the API call"""
    for permission in permissions_of_user:
        allowed_methods = permission.methods
        allowed_endpoints = permission.endpoints

        # check if any endpoints or methods allowed
        if allowed_endpoints is None or allowed_methods is None:
            continue

        # check if allowed based on the method
        if "*" not in allowed_methods and request.method not in allowed_methods:
            continue
        # prepare the uri
        prefix = "/api/{}".format(__api_version__)
        short_uri = request.uri.split(prefix, 1)[1].split("?", 1)[0]

        # check if you're permitted to make api call based on uri
        endpoint_matched = "*" in allowed_endpoints or _uri_matches_any_pattern(short_uri, allowed_endpoints)

        if not endpoint_matched:
            continue

        # check if the endpoint is excluded by this permission entry
        exclude_endpoints = permission.exclude_endpoints or []
        if exclude_endpoints and _uri_matches_any_pattern(short_uri, exclude_endpoints):
            continue

        return True

    return False
