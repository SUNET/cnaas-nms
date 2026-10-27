import base64
import json

import pytest
import requests

from cnaas_nms.app_settings import construct_auth_settings
from cnaas_nms.tools.oidc import oidc_client_call
from cnaas_nms.tools.oidc.token import Token

IDP = "https://idp.example.org"
CLIENT_TOKEN_INFO = {"active": True, "client_id": "dhcp-client"}


class FakeProvider(requests.adapters.BaseAdapter):
    """Identity provider that refuses userinfo and answers introspection only for one client at one endpoint"""

    def __init__(self, introspection_endpoint: str, client_id: str, client_secret: str):
        super().__init__()
        self.introspection_endpoint = introspection_endpoint
        self.authorization = "Basic " + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    def send(self, request, **kwargs):
        response = requests.Response()
        if request.url == IDP + "/.well-known/openid-configuration":
            response.status_code = 200
            body = {"userinfo_endpoint": IDP + "/userinfo", "introspection_endpoint": IDP + "/introspect"}
        elif request.url == self.introspection_endpoint and request.headers["Authorization"] == self.authorization:
            response.status_code = 200
            body = CLIENT_TOKEN_INFO
        else:
            response.status_code = 401
            body = {"error": "unauthorized"}
        response._content = json.dumps(body).encode()
        return response


@pytest.fixture
def token_info(monkeypatch):
    def introspect(provider: FakeProvider, **env: str) -> dict:
        monkeypatch.setattr(requests.Session, "get_adapter", lambda session, url: provider)
        monkeypatch.setenv("OIDC_CONF_WELL_KNOWN_URL", IDP + "/.well-known/openid-configuration")
        monkeypatch.setenv("OIDC_CLIENT_ID", "web-client")
        monkeypatch.setenv("OIDC_CLIENT_SECRET", "web-secret")
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        monkeypatch.setattr(oidc_client_call, "auth_settings", construct_auth_settings())
        return oidc_client_call.get_oauth_token_info(Token("client-credentials-token", {}))

    return introspect


def test_client_credentials_token_introspected_with_separate_credentials(token_info):
    provider = FakeProvider("https://introspect.example.org/introspect", "resource-server", "rs-secret")

    assert (
        token_info(
            provider,
            OIDC_INTROSPECT_URL="https://introspect.example.org/introspect",
            OIDC_INTROSPECT_CLIENT_ID="resource-server",
            OIDC_INTROSPECT_CLIENT_SECRET="rs-secret",
        )
        == CLIENT_TOKEN_INFO
    )


def test_client_credentials_token_introspected_as_login_client_by_default(token_info):
    provider = FakeProvider(IDP + "/introspect", "web-client", "web-secret")

    assert token_info(provider) == CLIENT_TOKEN_INFO
