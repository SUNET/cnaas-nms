from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseSettings, PostgresDsn, validator


class AppSettings(BaseSettings):
    # Database settings
    CNAAS_DB_HOSTNAME: str = "127.0.0.1"
    CNAAS_DB_USERNAME: str = "cnaas"
    CNAAS_DB_PASSWORD: str = "cnaas"
    CNAAS_DB_DATABASE: str = "cnaas"
    CNAAS_DB_PORT: int = 5432
    REDIS_HOSTNAME: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    POSTGRES_DSN: PostgresDsn = (
        f"postgresql://{CNAAS_DB_USERNAME}:{CNAAS_DB_PASSWORD}@{CNAAS_DB_HOSTNAME}:{CNAAS_DB_PORT}/{CNAAS_DB_DATABASE}"
    )
    USERNAME_INIT: str = "admin"
    PASSWORD_INIT: str = "abc123abc123"
    USERNAME_DHCP_BOOT: str = "admin"
    PASSWORD_DHCP_BOOT: str = "abc123abc123"
    USERNAME_DISCOVERED: str = "admin"
    PASSWORD_DISCOVERED: str = "abc123abc123"
    USERNAME_MANAGED: str = "admin"
    PASSWORD_MANAGED: str = "abc123abc123"
    TEMPLATES_REMOTE: str = "/opt/git/cnaas-templates-origin.git"
    TEMPLATES_LOCAL: str = "/opt/cnaas/templates"
    SETTINGS_REMOTE: str = "/opt/git/cnaas-settings-origin.git"
    SETTINGS_LOCAL: str = "/opt/cnaas/settings"


class ApiSettings(BaseSettings):
    # Api Settings
    HOST: str = "0.0.0.0"
    HTTPD_URL: str = "https://cnaas_httpd:1443/api/v1.0/firmware"
    VERIFY_TLS: bool = False
    VERIFY_TLS_DEVICE: bool = False
    JWT_CERT: Path = "/opt/cnaas/jwtcert/public.pem"
    CAFILE: Optional[Path] = "/opt/cnaas/cacert/rootCA.crt"
    CAKEYFILE: Path = "/opt/cnaas/cacert/rootCA.key"
    CERTPATH: Path = "/tmp/devicecerts/"
    ALLOW_APPLY_CONFIG_LIVERUN: bool = False
    FIRMWARE_URL: str = HTTPD_URL
    JWT_ENABLED: bool = True
    PLUGIN_FILE: Path = "/etc/cnaas-nms/plugins.yml"
    GLOBAL_UNIQUE_VLANS: bool = True
    INIT_MGMT_TIMEOUT: int = 30
    MGMTDOMAIN_RESERVED_COUNT: int = 5
    MGMTDOMAIN_PRIMARY_IP_VERSION: int = 4
    COMMIT_CONFIRMED_MODE: int = 1
    COMMIT_CONFIRMED_TIMEOUT: int = 300
    SETTINGS_OVERRIDE: Optional[dict] = None

    @validator("MGMTDOMAIN_PRIMARY_IP_VERSION")
    @classmethod
    def primary_ip_version_is_valid(cls, version: int) -> int:
        if version not in (4, 6):
            raise ValueError("must be either 4 or 6")
        return version


class AuthSettings(BaseSettings):
    # Authorization settings
    OIDC_CONF_WELL_KNOWN_URL: str = "well-known-openid-configuration-endpoint"
    OIDC_CLIENT_SECRET: str = "xxx"
    OIDC_CLIENT_ID: str = "client-id"
    FE_CALLBACK_URL: str = "http://localhost/callback"


def construct_api_settings() -> ApiSettings:
    api_config = Path("/etc/cnaas-nms/api.yml")

    if api_config.is_file():
        with open(api_config, "r") as api_file:
            config = yaml.safe_load(api_file)

        if config.get("firmware_url", False):
            firmware_url = config["firmware_url"]

        else:
            firmware_url = config["httpd_url"]
        return ApiSettings(
            HOST=config["host"],
            HTTPD_URL=config["httpd_url"],
            VERIFY_TLS=config["verify_tls"],
            VERIFY_TLS_DEVICE=config["verify_tls_device"],
            JWT_CERT=config.get("jwtcert", ApiSettings().JWT_CERT),
            CAFILE=config.get("cafile", ApiSettings().CAFILE),
            CAKEYFILE=config.get("cakeyfile", ApiSettings().CAKEYFILE),
            CERTPATH=config.get("certpath", ApiSettings().CERTPATH),
            FIRMWARE_URL=firmware_url,
            GLOBAL_UNIQUE_VLANS=config.get("global_unique_vlans", True),
            INIT_MGMT_TIMEOUT=config.get("init_mgmt_timeout", 30),
            MGMTDOMAIN_RESERVED_COUNT=config.get("mgmtdomain_reserved_count", 5),
            MGMTDOMAIN_PRIMARY_IP_VERSION=config.get("mgmtdomain_primary_ip_version", 4),
            COMMIT_CONFIRMED_MODE=config.get("commit_confirmed_mode", 1),
            COMMIT_CONFIRMED_TIMEOUT=config.get("commit_confirmed_timeout", 300),
            SETTINGS_OVERRIDE=config.get("settings_override", None),
        )
    else:
        return ApiSettings()


def construct_app_settings() -> AppSettings:
    db_config = Path("/etc/cnaas-nms/db_config.yml")
    repo_config = Path("/etc/cnaas-nms/repository.yml")

    app_settings = AppSettings()

    def _create_db_config(settings: AppSettings, config: dict) -> None:
        settings.CNAAS_DB_HOSTNAME = config["hostname"]
        settings.CNAAS_DB_USERNAME = config["username"]
        settings.CNAAS_DB_PORT = config["port"]
        settings.CNAAS_DB_DATABASE = config["database"]
        settings.CNAAS_DB_PASSWORD = config["password"]
        settings.REDIS_HOSTNAME = config["redis_hostname"]
        settings.POSTGRES_DSN = f"postgresql://{settings.CNAAS_DB_USERNAME}:{settings.CNAAS_DB_PASSWORD}@{settings.CNAAS_DB_HOSTNAME}:{settings.CNAAS_DB_PORT}/{settings.CNAAS_DB_DATABASE}"

    if db_config.is_file():
        with open(db_config, "r") as db_file:
            config = yaml.safe_load(db_file)
        _create_db_config(app_settings, config)

    def _create_repo_config(settings: AppSettings, config: dict) -> None:
        settings.TEMPLATES_REMOTE = config["templates_remote"]
        settings.TEMPLATES_LOCAL = config["templates_local"]
        settings.SETTINGS_REMOTE = config["settings_remote"]
        settings.SETTINGS_LOCAL = config["settings_local"]

    if repo_config.is_file():
        with open(repo_config, "r") as repo_file:
            config = yaml.safe_load(repo_file)
        _create_repo_config(app_settings, config)

    return app_settings


def construct_auth_settings() -> AuthSettings:
    auth_settings = AuthSettings()
    return auth_settings


app_settings = construct_app_settings()
api_settings = construct_api_settings()
auth_settings = construct_auth_settings()
