import yaml
from typing import Optional

from pydantic import BaseSettings, PostgresDsn
from pathlib import Path


class AppSettings(BaseSettings):

    # Database settings
    CNAAS_DB_HOSTNAME: str = "127.0.0.1"
    CNAAS_DB_USERNAME: str = "cnaas"
    CNAAS_DB_PASSWORD: str = "cnaas"
    CNAAS_DB_DATABASE: str = "cnaas"
    CNAAS_DB_PORT: int = 5432
    REDIS_HOSTNAME: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    POSTGRES_DSN: PostgresDsn = f"postgresql://{CNAAS_DB_USERNAME}:{CNAAS_DB_PASSWORD}@{CNAAS_DB_HOSTNAME}:{CNAAS_DB_PORT}/{CNAAS_DB_DATABASE}"


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
    OAUTH2_ENABLED: bool = True
    PLUGIN_FILE: Path = "/etc/cnaas-nms/plugins.yml"


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
            JWT_CERT=config["jwt_cert"],
            CAFILE=config["cafile"],
            CAKEYFILE=config["cakeyfile"],
            CERTPATH=config["certpath"],
            FIRMWARE_URL=firmware_url,
        )
    else:
        return ApiSettings()


def construct_app_settings() -> AppSettings:
    db_config = Path("/etc/cnaas-nms/db_config.yml")

    if db_config.is_file():
        with open(db_config, "r") as db_file:
            config = yaml.safe_load(db_file)
        return AppSettings(
            CNAAS_DB_HOSTNAME=config["hostname"],
            CNAAS_DB_USERNAME=config["username"],
            CNAAS_DB_PORT=config["port"],
            CNAAS_DB_DATABASE=config["database"],
            CNAAS_DB_PASSWORD=config["password"],
            REDIS_HOSTNAME=config["redis_hostname"],
        )
    else:
        return AppSettings()


app_settings = construct_app_settings()
api_settings = construct_api_settings()
