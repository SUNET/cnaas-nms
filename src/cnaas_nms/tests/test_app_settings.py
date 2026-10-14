import pytest

from cnaas_nms import app_settings

API_CONFIG = """
host: 0.0.0.0
httpd_url: https://httpd/firmware
verify_tls: false
verify_tls_device: false
global_unique_vlans: true
"""

DB_CONFIG = """
hostname: cnaas_postgres
port: 5433
username: nms
password: secret
database: nms
redis_hostname: cnaas_redis
"""


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Serve /etc/cnaas-nms from a temporary directory"""
    real_path = app_settings.Path
    monkeypatch.setattr(
        app_settings, "Path", lambda path: real_path(str(path).replace("/etc/cnaas-nms", str(tmp_path)))
    )
    return tmp_path


def test_env_overrides_api_yml(config_dir, monkeypatch):
    (config_dir / "api.yml").write_text(API_CONFIG)
    monkeypatch.setenv("GLOBAL_UNIQUE_VLANS", "false")
    assert app_settings.construct_api_settings().GLOBAL_UNIQUE_VLANS is False


def test_env_httpd_url_sets_firmware_url(config_dir, monkeypatch):
    (config_dir / "api.yml").write_text(API_CONFIG)
    monkeypatch.setenv("HTTPD_URL", "https://firmware.example.org/api/v1.0/firmware")
    assert app_settings.construct_api_settings().FIRMWARE_URL == "https://firmware.example.org/api/v1.0/firmware"


def test_env_dsn_overrides_db_config(config_dir, monkeypatch):
    (config_dir / "db_config.yml").write_text(DB_CONFIG)
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://cnaas:cnaas@db.example.org:5432/cnaas")
    assert app_settings.construct_app_settings().POSTGRES_DSN == "postgresql://cnaas:cnaas@db.example.org:5432/cnaas"


def test_env_db_hostname_overrides_db_config(config_dir, monkeypatch):
    (config_dir / "db_config.yml").write_text(DB_CONFIG)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.setenv("CNAAS_DB_HOSTNAME", "db.example.org")
    assert app_settings.construct_app_settings().POSTGRES_DSN == "postgresql://nms:secret@db.example.org:5433/nms"


def test_env_overrides_auth_config(config_dir, monkeypatch):
    (config_dir / "auth_config.yml").write_text("oidc_enabled: false\n")
    monkeypatch.setenv("OIDC_ENABLED", "true")
    monkeypatch.setenv("PERMISSIONS_DISABLED", "true")  # config_dir has no permissions.yml
    assert app_settings.construct_auth_settings().OIDC_ENABLED is True


def test_numeric_config_value_loads_as_string(config_dir, monkeypatch):
    (config_dir / "auth_config.yml").write_text("oidc_client_id: 1234567\n")
    monkeypatch.setenv("PERMISSIONS_DISABLED", "true")
    assert app_settings.construct_auth_settings().OIDC_CLIENT_ID == "1234567"


def test_repository_yml_applies_without_env(config_dir, monkeypatch):
    (config_dir / "repository.yml").write_text(
        "templates_remote: https://git.example.org/templates.git\ntemplates_local: /opt/cnaas/templates\n"
        "settings_remote: https://git.example.org/settings.git\nsettings_local: /opt/cnaas/settings\n"
    )
    monkeypatch.delenv("TEMPLATES_REMOTE", raising=False)
    assert app_settings.construct_app_settings().TEMPLATES_REMOTE == "https://git.example.org/templates.git"
