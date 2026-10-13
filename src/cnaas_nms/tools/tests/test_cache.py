import json
import time

import pytest

from cnaas_nms.db.session import redis_session
from cnaas_nms.tools.cache import REDIS_OAUTH_TOKEN_INFO_KEY, get_token_info_from_cache, put_token_info_in_cache
from cnaas_nms.tools.oidc.token import Token


@pytest.fixture(autouse=True)
def empty_token_cache(redis):
    with redis_session() as conn:  # type: ignore
        conn.delete(REDIS_OAUTH_TOKEN_INFO_KEY)


def make_token(token_string: str, sub: str) -> Token:
    return Token(token_string, {"sub": sub, "exp": int(time.time()) + 300})


def test_cached_token_info_only_answers_for_its_own_token():
    frontend_token = make_token("token-from-frontend", sub="alice")
    script_token = make_token("token-from-script", sub="alice")
    frontend_info = {"sub": "alice", "client_id": "frontend", "groups": ["netadmin"]}

    put_token_info_in_cache(frontend_token, json.dumps(frontend_info))

    assert get_token_info_from_cache(frontend_token) == frontend_info
    assert get_token_info_from_cache(script_token) is None


def test_bearer_token_is_not_stored_in_redis():
    token = make_token("secret-bearer-token", sub="alice")

    put_token_info_in_cache(token, json.dumps({"sub": "alice"}))

    assert get_token_info_from_cache(token) == {"sub": "alice"}
    with redis_session() as conn:  # type: ignore
        stored = list(conn.scan_iter())
        for name in conn.scan_iter(_type="hash"):
            stored += [text for item in conn.hgetall(name).items() for text in item]
    assert not any(token.token_string in text for text in stored)
