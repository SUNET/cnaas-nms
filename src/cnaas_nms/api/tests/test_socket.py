import pytest
from pydantic import ValidationError

from cnaas_nms.api.models.socket import (
    LOG_LEVELS,
    LogLevel,
    SocketSubscription,
    SyncRoom,
    UpdateRoom,
)


class TestLogLevel:
    def test_log_levels_ordering(self):
        assert LOG_LEVELS == [
            LogLevel.DEBUG,
            LogLevel.INFO,
            LogLevel.WARNING,
            LogLevel.ERROR,
            LogLevel.CRITICAL,
        ]

    def test_log_level_is_str(self):
        assert LogLevel.DEBUG == "DEBUG"
        assert isinstance(LogLevel.DEBUG, str)


class TestUpdateRoom:
    def test_update_room_values(self):
        assert UpdateRoom.DEVICE == "update_device"
        assert UpdateRoom.JOB == "update_job"


class TestSyncRoom:
    def test_sync_room_value(self):
        assert SyncRoom.ALL == "sync"


class TestSocketSubscription:
    # Valid subscriptions
    def test_valid_loglevel(self):
        sub = SocketSubscription(loglevel="DEBUG")
        assert sub.loglevel == "DEBUG"

    def test_valid_update_device(self):
        sub = SocketSubscription(update="device")
        assert sub.update == "device"

    def test_valid_update_job(self):
        sub = SocketSubscription(update="job")
        assert sub.update == "job"

    def test_valid_sync(self):
        sub = SocketSubscription(sync="all")
        assert sub.sync == "all"

    # Invalid values
    def test_invalid_loglevel(self):
        with pytest.raises(ValidationError, match="Invalid loglevel"):
            SocketSubscription(loglevel="BANANA")

    def test_invalid_update_type(self):
        with pytest.raises(ValidationError, match="Invalid update type"):
            SocketSubscription(update="banana")

    def test_invalid_sync_value(self):
        with pytest.raises(ValidationError, match="Invalid sync value"):
            SocketSubscription(sync="banana")

    # Exactly one field
    def test_no_fields_rejected(self):
        with pytest.raises(ValidationError, match="Exactly one"):
            SocketSubscription()

    def test_multiple_fields_rejected(self):
        with pytest.raises(ValidationError, match="Exactly one"):
            SocketSubscription(loglevel="DEBUG", sync="all")

    def test_all_fields_rejected(self):
        with pytest.raises(ValidationError, match="Exactly one"):
            SocketSubscription(loglevel="DEBUG", update="device", sync="all")

    # to_room
    def test_to_room_loglevel(self):
        sub = SocketSubscription(loglevel="DEBUG")
        assert sub.to_room() == LogLevel.DEBUG

    def test_to_room_loglevel_critical(self):
        sub = SocketSubscription(loglevel="CRITICAL")
        assert sub.to_room() == LogLevel.CRITICAL

    def test_to_room_update_device(self):
        sub = SocketSubscription(update="device")
        assert sub.to_room() == UpdateRoom.DEVICE

    def test_to_room_update_job(self):
        sub = SocketSubscription(update="job")
        assert sub.to_room() == UpdateRoom.JOB

    def test_to_room_sync(self):
        sub = SocketSubscription(sync="all")
        assert sub.to_room() == SyncRoom.ALL

    # All valid log levels
    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    def test_all_loglevels_valid(self, level):
        sub = SocketSubscription(loglevel=level)
        assert sub.to_room() == LogLevel(level)
