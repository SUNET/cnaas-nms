from unittest.mock import MagicMock, patch

import pytest

from cnaas_nms.devicehandler.fencing import (
    REDIS_FENCING_TOKENS_KEY,
    FencingError,
    create_syncto_fencing_token,
    delete_all_fencing_tokens,
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
    def test_creates_token_in_redis_set(self, mock_redis):
        create_syncto_fencing_token(42)

        mock_redis.sadd.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, "42")

    def test_sets_ttl_on_key(self, mock_redis):
        create_syncto_fencing_token(42)

        mock_redis.expire.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, 7200)

    def test_converts_job_id_to_string(self, mock_redis):
        create_syncto_fencing_token(12345)

        mock_redis.sadd.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, "12345")

    def test_raises_on_redis_error(self):
        from redis.exceptions import RedisError

        with patch("cnaas_nms.devicehandler.fencing.redis_session") as mock_session:
            mock_client = MagicMock()
            mock_client.sadd.side_effect = RedisError("connection failed")
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(RedisError):
                create_syncto_fencing_token(42)


class TestGetFencingToken:
    def test_returns_true_when_token_exists(self, mock_redis):
        mock_redis.sismember.return_value = True

        result = get_fencing_token("42")

        assert result is True
        mock_redis.sismember.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, "42")

    def test_returns_false_when_token_missing(self, mock_redis):
        mock_redis.sismember.return_value = False

        result = get_fencing_token("99")

        assert result is False

    def test_converts_input_to_string(self, mock_redis):
        mock_redis.sismember.return_value = True

        get_fencing_token("123")

        mock_redis.sismember.assert_called_once_with(REDIS_FENCING_TOKENS_KEY, "123")

    def test_raises_on_redis_error(self):
        from redis.exceptions import RedisError

        with patch("cnaas_nms.devicehandler.fencing.redis_session") as mock_session:
            mock_client = MagicMock()
            mock_client.sismember.side_effect = RedisError("connection failed")
            mock_session.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(RedisError):
                get_fencing_token("42")


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
        mock_redis.sismember.return_value = True

        create_syncto_fencing_token(42)
        result = get_fencing_token("42")

        assert result is True

    def test_create_then_delete_then_get_returns_false(self, mock_redis):
        mock_redis.sismember.return_value = False
        mock_redis.delete.return_value = 1

        create_syncto_fencing_token(42)
        delete_all_fencing_tokens()
        result = get_fencing_token("42")

        assert result is False

    def test_multiple_tokens_all_deleted(self, mock_redis):
        """Verifying that delete_all removes tokens for all job_ids."""
        mock_redis.delete.return_value = 1

        create_syncto_fencing_token(1)
        create_syncto_fencing_token(2)
        create_syncto_fencing_token(3)
        delete_all_fencing_tokens()

        # Single DEL call removes the entire SET (all tokens at once)
        mock_redis.delete.assert_called_once_with(REDIS_FENCING_TOKENS_KEY)
