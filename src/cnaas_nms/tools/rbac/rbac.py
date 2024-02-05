import fnmatch
from typing import List

from authlib.integrations.flask_oauth2.requests import FlaskJsonRequest

from cnaas_nms.models.permissions import PermissionModel, PermissionsModel
from cnaas_nms.version import __api_version__


def get_permissions_user(permissions_rules: PermissionsModel, user_info: dict):
    """Get the API permissions of the user"""
    permissions_of_user = []

    # if no rules, return
    if not permissions_rules:
        return permissions_of_user

    # first give all the permissions of the fallback role
    if permissions_rules.config and permissions_rules.config.default_permissions:
        permissions_of_user.extend(
            permissions_rules.roles.get(permissions_rules.config.default_permissions).permissions
        )

    user_roles: List[str] = []
    # read the group mappings and add the relevant roles
    if permissions_rules.group_mappings:
        map_type: str
        mappings: dict[str, list[str]]
        for map_type, mappings in permissions_rules.group_mappings.items():
            for value, groups in mappings.items():
                if value in user_info[map_type]:
                    user_roles.extend(groups)

    # find the relevant roles and add permissions
    relevant_roles = list(set(permissions_rules.roles) & set(user_roles))
    for relevant_role in relevant_roles:
        permissions_of_user.extend(permissions_rules.roles[relevant_role].permissions)

    return permissions_of_user


def check_if_api_call_is_permitted(request: FlaskJsonRequest, permissions_of_user: list[PermissionModel]):
    """Checks if the user has permission to execute the API call"""
    for permission in permissions_of_user:
        allowed_methods = permission.methods
        allowed_endpoints = permission.endpoints

        # check if allowed based on the method
        if "*" not in allowed_methods and request.method not in allowed_methods:
            continue

        # prepare the uri
        prefix = "/api/{}".format(__api_version__)
        short_uri = request.uri.split(prefix, 1)[1].split("?", 1)[0]

        # check if you're permitted to make api call based on uri
        if "*" in allowed_endpoints or short_uri in allowed_endpoints:
            return True

        # added the glob patterns so it's easier to add a bunch of api calls (like all /device api calls)
        for allowed_api_call in allowed_endpoints:
            matches = fnmatch.filter([short_uri], allowed_api_call)
            if len(matches) > 0:
                return True

    return False
