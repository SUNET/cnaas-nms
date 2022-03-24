from typing import Optional, List
from pydantic import BaseModel, validator, conint


class StackmemberModel(BaseModel):
    member_no: Optional[conint(gt=-1)] = None
    hardware_id: str
    priority: Optional[conint(gt=-1)] = None

    @validator("hardware_id")
    def validate_non_empty_hardware_id(cls, hardware_id):
        """Validate that hardware_id is not an empty string."""
        if not hardware_id:
            raise ValueError("hardware_id cannot be an empty string")
        return hardware_id


class StackmembersModel(BaseModel):
    stackmembers: List[StackmemberModel]

    @validator("stackmembers")
    def validate_unique_member_no(cls, stackmembers):
        """Validate that all StackmemberModel in stackmembers have unique member_no compared to each other."""
        member_no_count = len({stackmember.member_no for stackmember in stackmembers})
        if member_no_count != len(stackmembers):
            raise ValueError("member_no must be unique for stackmembers belonging to the same device")
        return stackmembers

    @validator("stackmembers")
    def validate_unique_hardware_id(cls, stackmembers):
        """Validate that all StackmemberModel in stackmembers have unique hardware_id compared to each other."""
        hardware_id_count = len({stackmember.hardware_id for stackmember in stackmembers})
        if hardware_id_count != len(stackmembers):
            raise ValueError("hardware_id must be unique for stackmembers belonging to the same device")
        return stackmembers
