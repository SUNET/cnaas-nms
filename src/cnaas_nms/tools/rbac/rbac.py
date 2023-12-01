import re

from authlib.oauth2.rfc6749.wrappers import HttpRequest

from cnaas_nms.version import __api_version__

#TODO rename?
def get_permissions_user(permissions_rules, user_info):
    '''Get the API permissions of the user'''
    permissions_of_user = {}
    # if no rules, return
    if len(permissions_rules) == 0:
        return permissions_of_user
    
    # first give all the permissions of the fallback role
    if "default_permissions" in permissions_rules["config"] and permissions_rules["config"]["default_permissions"] in permissions_rules["roles"]:
        permissions_of_user[permissions_rules["config"]["default_permissions"]] = permissions_rules["roles"][permissions_rules["config"]["default_permissions"]]
    
    # if the element is not defined or the user doesn't have the element, return
    if 'role_in_jwt_element' not in permissions_rules['config'] or permissions_rules['config']['role_in_jwt_element'] not in user_info:
        return permissions_of_user
    
    # make the roles of userinfo into the right format, a list of roles
    if isinstance(user_info[permissions_rules['config']['role_in_jwt_element']], list):
        if 'roles_separated_by' in permissions_rules['config']:
            user_roles = []
            for item in user_info[permissions_rules['config']['role_in_jwt_element']]:
                user_roles.extend(item.split(permissions_rules['config']['roles_separated_by']))
        else:
            user_roles = user_info[permissions_rules['config']['role_in_jwt_element']]
    elif 'roles_separated_by' in permissions_rules['config']:
        user_roles = user_info[permissions_rules['config']['role_in_jwt_element']].split(permissions_rules['config']['roles_separated_by'])
    else:
        user_roles = [user_info[permissions_rules['config']['role_in_jwt_element']]]

    # find the relevant roles and add permissions 
    relevant_roles = list(set(permissions_rules["roles"]) & set(user_roles))
    for relevant_role in relevant_roles:
        permissions_of_user[relevant_role] = permissions_rules["roles"][relevant_role]
    
    return permissions_of_user


def check_if_api_call_is_permitted(request: HttpRequest, permissions_of_user):
    '''Checks if the user has permission to execute the API call'''
    for role in permissions_of_user:
        allowed_api_methods = permissions_of_user[role]['allowed_api_methods']
        allowed_api_calls = permissions_of_user[role]['allowed_api_calls']

        # check if allowed based on the method
        if "*" not in allowed_api_methods and request.method not in allowed_api_methods:
            continue

        # check if you're permitted to make api call based on uri
        prefix = "/api/{}".format(__api_version__)
        short_uri = request.uri[:-1].strip().removeprefix(prefix)
        if "*" not in allowed_api_calls and short_uri not in allowed_api_calls:
            # added the regex so it's easier to add a bunch of api calls (like all /device api calls)
            combined = "(" + ")|(".join(allowed_api_calls) + ")"
            try:
                re.compile(combined)
            except re.error:
                continue
            if not re.fullmatch(combined, short_uri):
                continue

        # api call is allowed, return true
        return True 
    return False