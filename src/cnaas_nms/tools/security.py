from flask_jwt_extended import jwt_required as jwt_orig

from cnaas_nms.app_settings import api_settings


def jwt_required(fn):
    """
    This function enables development without Oauth.

    """
    if api_settings.OAUTH2_ENABLED:
        return jwt_orig(fn)
    else:
        return fn
