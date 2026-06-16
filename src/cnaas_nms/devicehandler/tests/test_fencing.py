import json
from unittest.mock import MagicMock, patch

import pytest

from cnaas_nms.devicehandler.fencing import (
    REDIS_FENCING_TOKENS_KEY,
    FencingError,
    create_syncto_fencing_token,
    delete_all_fencing_tokens,
    delete_fencing_token,
    get_fencing_token,
)


@pytest.fixture
def mock_redis():
    """Provide a mock Redis client via the redis_session context manager."""
    mock_client = MagicMock()
    with patch("cnaas_nms.devicehandler.fencing.redis_session") as mock_session:
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_client


class TestCreateSynctoFencingToken:
    def test_creates_token_in_redis_hash(self, mock_redis):
        create_syncto_fencing_token(42, ["host1", "host2"])

        mock_redis.hset.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, "42", json.dumps(["host1", "host2"]))

    def test_sets_ttl_on_key(self, mock_redis):
        create_syncto_fencing_token(42, ["host1"])

        mock_redis.expire.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, 7200)

    def test_converts_job_id_to_string(self, mock_redis):
        create_syncto_fencing_token(12345, ["host1"])

        mock_redis.hset.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, "12345", json.dumps(["host1"]))

    def test_stores_empty_device_list(self, mock_redis):
        create_syncto_fencing_token(42, [])

        mock_redis.hset.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, "42", json.dumps([]))

    def test_raises_on_redis_error(self):
        from redis.exceptions import RedisError

        with patch("cnaas_nms.devicehandler.fencing.redis_session") as mock_session:
            mock_client = MagicMock()
            mock_client.hset.side_effect = RedisError("connection failed")
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(RedisError):
                create_syncto_fencing_token(42, ["host1"])


class TestGetFencingToken:
    def test_returns_true_when_token_exists(self, mock_redis):
        mock_redis.hexists.return_value = True

        result = get_fencing_token(42)

        assert result is True
        mock_redis.hexists.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, "42")

    def test_returns_false_when_token_missing(self, mock_redis):
        mock_redis.hexists.return_value = False

        result = get_fencing_token(99)

        assert result is False

    def test_converts_int_to_string_for_redis(self, mock_redis):
        mock_redis.hexists.return_value = True

        get_fencing_token(123)

        mock_redis.hexists.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, "123")

    def test_raises_on_redis_error(self):
        from redis.exceptions import RedisError

        with patch("cnaas_nms.devicehandler.fencing.redis_session") as mock_session:
            mock_client = MagicMock()
            mock_client.hexists.side_effect = RedisError("connection failed")
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(RedisError):
                get_fencing_token(42)


class TestDeleteFencingToken:
    def test_deletes_token_containing_hostname(self, mock_redis):
        mock_redis.hgetall.return_value = {
            "42": json.dumps(["host1", "host2"]),
            "43": json.dumps(["host3"]),
        }

        delete_fencing_token("host1")

        mock_redis.hdel.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, "42")

    def test_deletes_multiple_tokens_containing_hostname(self, mock_redis):
        mock_redis.hgetall.return_value = {
            "42": json.dumps(["host1", "host2"]),
            "43": json.dumps(["host1", "host3"]),
            "44": json.dumps(["host4"]),
        }

        delete_fencing_token("host1")

        assert mock_redis.hdel.call_count == 2
        mock_redis.hdel.assert_any_call(REDIS_FENCING_TOKENS_KEY, "42")
        mock_redis.hdel.assert_any_call(REDIS_FENCING_TOKENS_KEY, "43")

    def test_does_not_delete_tokens_without_hostname(self, mock_redis):
        mock_redis.hgetall.return_value = {
            "42": json.dumps(["host1", "host2"]),
            "43": json.dumps(["host3"]),
        }

        delete_fencing_token("host3")

        mock_redis.hdel.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, "43")

    def test_does_nothing_when_no_tokens_exist(self, mock_redis):
        mock_redis.hgetall.return_value = {}

        delete_fencing_token("host1")

        mock_redis.hdel.assert_not_called()

    def test_does_nothing_when_hostname_not_in_any_token(self, mock_redis):
        mock_redis.hgetall.return_value = {
            "42": json.dumps(["host1", "host2"]),
        }

        delete_fencing_token("host99")

        mock_redis.hdel.assert_not_called()

    def test_does_not_raise_on_redis_error(self):
        """delete_fencing_token logs but does not re-raise Redis errors."""
        from redis.exceptions import RedisError

        with patch("cnaas_nms.devicehandler.fencing.redis_session") as mock_session:
            mock_client = MagicMock()
            mock_client.hgetall.side_effect = RedisError("connection failed")
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            # Should not raise - delete_fencing_token only logs the error
            delete_fencing_token("host1")


class TestDeleteAllFencingTokens:
    def test_deletes_the_redis_key(self, mock_redis):
        mock_redis.delete.return_value = 1

        delete_all_fencing_tokens()

        mock_redis.delete.assert_called_once_with(REDIS_FENCING_TOKENS_KEY)

    def test_does_not_raise_when_key_does_not_exist(self, mock_redis):
        mock_redis.delete.return_value = 0

        # Should not raise
        delete_all_fencing_tokens()

        mock_redis.delete.assert_called_once_with(REDIS_FENCING_TOKENS_KEY)

    def test_does_not_raise_on_redis_error(self):
        """delete_all_fencing_tokens logs but does not re-raise Redis errors."""
        from redis.exceptions import RedisError

        with patch("cnaas_nms.devicehandler.fencing.redis_session") as mock_session:
            mock_client = MagicMock()
            mock_client.delete.side_effect = RedisError("connection failed")
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            # Should not raise - delete_all_fencing_tokens only logs the error
            delete_all_fencing_tokens()


class TestFencingError:
    def test_is_exception_subclass(self):
        assert issubclass(FencingError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(FencingError, match="token 42 is invalid"):
            raise FencingError("token 42 is invalid")


class TestFencingTokenWorkflow:
    """Integration-style tests verifying the complete fencing token workflow."""

    def test_create_then_get_returns_true(self, mock_redis):
        mock_redis.hexists.return_value = True

        create_syncto_fencing_token(42, ["host1"])
        result = get_fencing_token(42)

        assert result is True

    def test_create_then_delete_by_hostname_invalidates_token(self, mock_redis):
        mock_redis.hexists.return_value = False
        mock_redis.hgetall.return_value = {"42": json.dumps(["host1", "host2"])}

        create_syncto_fencing_token(42, ["host1", "host2"])
        delete_fencing_token("host1")
        result = get_fencing_token(42)

        assert result is False
        mock_redis.hdel.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, "42")

    def test_unrelated_hostname_does_not_invalidate_token(self, mock_redis):
        mock_redis.hexists.return_value = True
        mock_redis.hgetall.return_value = {"42": json.dumps(["host1", "host2"])}

        create_syncto_fencing_token(42, ["host1", "host2"])
        delete_fencing_token("host99")
        result = get_fencing_token(42)

        assert result is True
        mock_redis.hdel.assert_not_called()

    def test_delete_all_removes_all_tokens(self, mock_redis):
        mock_redis.delete.return_value = 1

        create_syncto_fencing_token(1, ["host1"])
        create_syncto_fencing_token(2, ["host2"])
        create_syncto_fencing_token(3, ["host3"])
        delete_all_fencing_tokens()

        mock_redis.delete.assert_called_once_with(REDIS_FENCING_TOKENS_KEY)
