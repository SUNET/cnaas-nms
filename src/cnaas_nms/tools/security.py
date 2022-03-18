from flask_jwt_extended import jwt_required as jwt_orig, get_jwt_identity as get_jwt_identity_orig

from cnaas_nms.app_settings import api_settings


def jwt_required(fn):
    """
    This function enables development without Oauth.

    """
    if api_settings.JWT_ENABLED:
        return jwt_orig()(fn)
    else:
        return fn


def get_jwt_identity():
    """
    This function overides the identity when needed.

    """
    return get_jwt_identity_orig() if api_settings.JWT_ENABLED else "admin"
