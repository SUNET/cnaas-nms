import re
from enum import Enum
from functools import cached_property
from typing import Annotated, Dict, List, Optional, Self

from pydantic import BaseModel, ValidationInfo, field_validator, model_validator
from pydantic.functional_validators import AfterValidator

from cnaas_nms.db.device import Device
from cnaas_nms.db.settings_fields.shared import group_name, group_priority_schema
from cnaas_nms.tools.log import get_logger


class f_group_device_filter(BaseModel):
    hostname: Optional[str] = None
    device_type: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None
    platform: Optional[str] = None

    @field_validator("hostname", "device_type", "model", "os_version", "platform")
    @classmethod
    def validate_regex(cls, v):
        """Validate that the value is a valid regex pattern."""
        if v is None:
            return v
        try:
            # Try compiling regex
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"Invalid regex pattern: {v}") from exc
        return v

    @cached_property
    def compiled_patterns(self) -> Dict[str, re.Pattern]:
        """
        Is a cached property to avoid re-compiling regex patterns
        """
        fields = set(self.__annotations__.keys())
        compiled_patterns = {}
        for field in fields:
            pattern = getattr(self, field, None)
            if pattern:
                compiled_patterns.update({field: re.compile(pattern)})
        return compiled_patterns

    def matches(self, device: Device) -> bool:
        """
        A function that matches a device based on the regex patterns.
        """
        compiled_patterns = self.compiled_patterns
        # No patterns defined, match nothing
        if not compiled_patterns:
            return False

        for field, pattern in compiled_patterns.items():
            value = getattr(device, field, None)
            if value is None:
                return False  # field missing → no match
            if isinstance(value, Enum):
                match_value = value.name
            else:
                match_value = value
            if not pattern.match(str(match_value)):  # convert to str to be safe
                return False  # pattern did not match
        return True  # all matched


class f_group(BaseModel):
    name: str = group_name
    device_filter: Optional[f_group_device_filter] = None
    devices: Optional[List[str]] = None
    group_priority: int = group_priority_schema
    templates_branch: Optional[str] = None

    def __init__(self, **data):
        logger = get_logger()
        if "group" in data:
            logger.warning(
                "Old group config style is deprecated and will be removed in a future version.",
            )
            legacy_data = data.pop("group")
            # Convert legacy group data to new format
            data["name"] = legacy_data.pop("name")
            regex = legacy_data.pop("regex")
            if regex:
                data["device_filter"] = {"hostname": regex}
            data["group_priority"] = legacy_data.pop("group_priority", 0)
            data["templates_branch"] = legacy_data.pop("templates_branch", None)
        super().__init__(**data)

    @field_validator("group_priority")
    @classmethod
    def reserved_priority(cls, v: int, info: ValidationInfo):
        if v and v == 1 and info.data["name"] != "DEFAULT":
            raise ValueError("group_priority 1 is reserved for built-in group DEFAULT")
        return v

    @field_validator("templates_branch")
    @classmethod
    def templates_branch_primary_group_only(cls, v: str, info: ValidationInfo):
        if v and info.data["group_priority"] <= 1:
            raise ValueError("templates_branch can only be specified on primary groups")
        return v

    @model_validator(mode="after")
    def cannot_use_device_filter_with_devices(self: Self) -> Self:
        device_filter = self.device_filter
        devices = self.devices
        if device_filter and devices:
            raise ValueError("cannot use device_filter together with devices")

        return self

    def matches(self, device: Device) -> bool:
        """A function to check if a device matches the group filters."""
        if self.device_filter is not None:
            # Use the device filter matcher to check if the device matches
            return self.device_filter.matches(device)
        elif self.devices is not None:
            # If no device filter is defined, check if the device is in the devices list
            return device.hostname in self.devices
        return False


def validate_groups(groups: List[f_group]):
    """
    Validate that the provided list of groups have unique names and group priorities.
    """

    # Validate uniqueness of group names and group priorities
    unique_fields = ["name", "group_priority"]
    for unique_field in unique_fields:
        seen = set()
        for group in groups:
            value = getattr(group, unique_field)
            # Skip validation for group_priority if it's 0
            if unique_field == "group_priority" and value == 0:
                continue
            if value in seen:
                raise ValueError(
                    f"Groups must have unique {unique_field} values, "
                    f"but group {group} has a duplicate {unique_field} value as another group."
                )
            seen.add(value)

    return groups


class f_groups(BaseModel):
    groups: Annotated[Optional[List[f_group]], AfterValidator(validate_groups)] = None
