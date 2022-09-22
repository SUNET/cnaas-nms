def pytest_configure(config):
    # Disable JWT tokens during unit testing (since app defaults want to load from global paths)
    from cnaas_nms.app_settings import api_settings
    api_settings.JWT_ENABLED = False
