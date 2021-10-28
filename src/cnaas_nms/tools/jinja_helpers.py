"""Functions that aid in the building of Jinja template contexts"""
import os


def get_environment_secrets(prefix="TEMPLATE_SECRET_"):
    """Returns a dictionary of secrets stored in environment variables"""
    template_secrets = {env: value for env, value in os.environ.items() if env.startswith(prefix)}

    return template_secrets
