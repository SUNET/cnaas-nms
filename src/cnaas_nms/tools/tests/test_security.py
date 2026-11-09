import pytest
from jose import jwt
from jwt.exceptions import InvalidTokenError

from cnaas_nms.app_settings import construct_auth_settings
from cnaas_nms.tools import security

SIGNING_KEY = "token-signing-key"


@pytest.fixture
def authenticate(monkeypatch):
    monkeypatch.setenv("OIDC_ENABLED", "True")
    monkeypatch.setenv("OIDC_CLIENT_ID", "web-client")
    monkeypatch.setenv("ADDITIONAL_AUDIENCES", '["dhcp-client"]')
    monkeypatch.setattr(security, "auth_settings", construct_auth_settings())
    monkeypatch.setattr(security, "get_key", lambda kid: SIGNING_KEY)

    def authenticate(claims: dict) -> dict:
        token_string = jwt.encode({"sub": "someone", **claims}, SIGNING_KEY, algorithm="HS256")
        return security.MyBearerTokenValidator().authenticate_token(token_string).decoded_token

    return authenticate


@pytest.mark.parametrize(
    "claims", [{"aud": "web-client"}, {"aud": "dhcp-client"}, {"aud": ["other-client", "dhcp-client"]}]
)
def test_token_for_accepted_audience_is_valid(authenticate, claims):
    assert authenticate(claims)["sub"] == "someone"


@pytest.mark.parametrize("claims", [{"aud": "other-client"}, {}])
def test_token_for_other_or_no_audience_is_rejected(authenticate, claims):
    with pytest.raises(InvalidTokenError):
        authenticate(claims)
