"""Functions that aid in the building of Jinja template contexts"""
import os


def get_environment_secrets(prefix="TEMPLATE_SECRET_"):
    """Returns a dictionary of secrets stored in environment variables"""
    template_secrets = {env: value for env, value in os.environ.items() if env.startswith(prefix)}
    # Also make secrets available as a dict, so keys can be constructed dynamically in templates
    template_secrets["TEMPLATE_SECRET"] = {env.replace(prefix, ""): value for env, value in template_secrets.items()}

    return template_secrets
