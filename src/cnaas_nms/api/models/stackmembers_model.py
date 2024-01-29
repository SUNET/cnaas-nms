from typing import List, Optional

from pydantic import BaseModel, conint, field_validator


class StackmemberModel(BaseModel):
    member_no: Optional[conint(gt=-1)] = None
    hardware_id: str
    priority: Optional[conint(gt=-1)] = None

    @field_validator("hardware_id")
    @classmethod
    def validate_non_empty_hardware_id(cls, hardware_id):
        """Validates that hardware_id is not an empty string"""
        if not hardware_id:
            raise ValueError("hardware_id cannot be an empty string")
        return hardware_id


class StackmembersModel(BaseModel):
    stackmembers: List[StackmemberModel]

    @field_validator("stackmembers")
    @classmethod
    def validate_unique_member_no(cls, stackmembers):
        """Validates that all StackmemberModel in stackmembers have unique member_no compared to each other"""
        member_no_count = len(set([stackmember.member_no for stackmember in stackmembers]))
        if member_no_count != len(stackmembers):
            raise ValueError("member_no must be unique for stackmembers belonging to the same device")
        return stackmembers

    @field_validator("stackmembers")
    @classmethod
    def validate_unique_hardware_id(cls, stackmembers):
        """Validates that all StackmemberModel in stackmembers have unique hardware_id compared to each other"""
        hardware_id_count = len(set([stackmember.hardware_id for stackmember in stackmembers]))
        if hardware_id_count != len(stackmembers):
            raise ValueError("hardware_id must be unique for stackmembers belonging to the same device")
        return stackmembers
