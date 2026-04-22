from enum import StrEnum

from pydantic import BaseModel, field_validator, model_validator


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


LOG_LEVELS = list(LogLevel)


class UpdateRoom(StrEnum):
    DEVICE = "update_device"
    JOB = "update_job"


class SyncRoom(StrEnum):
    ALL = "sync"


class SocketSubscription(BaseModel):
    loglevel: str | None = None
    update: str | None = None
    sync: str | None = None

    @field_validator("loglevel")
    @classmethod
    def validate_loglevel(cls, v: str | None) -> str | None:
        if v is not None:
            valid = [e.value for e in LogLevel]
            if v not in valid:
                raise ValueError(f"Invalid loglevel: {v}. Must be one of {valid}")
        return v

    @field_validator("update")
    @classmethod
    def validate_update(cls, v: str | None) -> str | None:
        if v is not None:
            valid_inputs = [e.value.removeprefix("update_") for e in UpdateRoom]
            if v not in valid_inputs:
                raise ValueError(f"Invalid update type: {v}. Must be one of {valid_inputs}")
        return v

    @field_validator("sync")
    @classmethod
    def validate_sync(cls, v: str | None) -> str | None:
        if v is not None and v != "all":  # room name does not match payload
            raise ValueError(f"Invalid sync value: {v}")
        return v

    @model_validator(mode="after")
    def exactly_one_field(self):
        set_fields = [f for f in (self.loglevel, self.update, self.sync) if f is not None]
        if len(set_fields) != 1:
            raise ValueError("Exactly one of loglevel, update, or sync must be set")
        return self

    def to_room(self) -> LogLevel | UpdateRoom | SyncRoom:
        if self.loglevel:
            return LogLevel(self.loglevel)
        elif self.update:
            return UpdateRoom(f"update_{self.update}")
        else:
            return SyncRoom.ALL
