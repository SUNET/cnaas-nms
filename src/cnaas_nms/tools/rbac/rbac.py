import fnmatch
from authlib.oauth2.rfc6749.wrappers import HttpRequest

from cnaas_nms.version import __api_version__

def get_permissions_user(permissions_rules, user_info):
    '''Get the API permissions of the user'''
    permissions_of_user = []

    # if no rules, return
    if not permissions_rules:
        return permissions_of_user
    
    # first give all the permissions of the fallback role
    if "default_permissions" in permissions_rules["config"] and permissions_rules["config"]["default_permissions"] in permissions_rules["roles"]:
        permissions_of_user.extend(permissions_rules["roles"][permissions_rules["config"]["default_permissions"]]["permissions"])
    
    # if the element is not defined or the user doesn't have the element, return
    if 'group_claim_key' not in permissions_rules['config'] or permissions_rules['config']['group_claim_key'] not in user_info:
        return permissions_of_user
    
    # make the roles of userinfo into the right format, a list of roles
    if isinstance(user_info[permissions_rules['config']['group_claim_key']], list):
        user_roles = user_info[permissions_rules['config']['group_claim_key']]
    else:
        user_roles = [user_info[permissions_rules['config']['group_claim_key']]]

    # find the relevant roles and add permissions 
    relevant_roles = list(set(permissions_rules["roles"]) & set(user_roles))
    for relevant_role in relevant_roles:
        permissions_of_user.extend(permissions_rules["roles"][relevant_role]["permissions"])

    return permissions_of_user


def check_if_api_call_is_permitted(request: HttpRequest, permissions_of_user):
    '''Checks if the user has permission to execute the API call'''
    for permission in permissions_of_user:
        allowed_methods = permission['methods']
        allowed_endpoints = permission['endpoints']

        # check if allowed based on the method
        if "*" not in allowed_methods and request.method not in allowed_methods:
            continue

        # prepare the uri
        prefix = "/api/{}".format(__api_version__)
        short_uri = request.uri.strip().removeprefix(prefix).split('?', 1)[0]

        # check if you're permitted to make api call based on uri
        if "*" in allowed_endpoints or short_uri in allowed_endpoints:
            return True
        
         # added the glob patterns so it's easier to add a bunch of api calls (like all /device api calls)
        for allowed_api_call in allowed_endpoints:
            matches = fnmatch.filter([short_uri], allowed_api_call)
            if len(matches) > 0:
                return True

    return False