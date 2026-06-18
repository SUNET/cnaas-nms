import datetime  # noqa: F401
import re
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from typing import Dict, List, Literal, Optional

import jmespath
from aerleon.lib.policy_builder import TermsList
from jmespath.exceptions import ParseError
from netutils.lib_mapper import AERLEON_LIB_MAPPER, NAPALM_LIB_MAPPER
from pydantic import BaseModel, TypeAdapter, field_validator

from cnaas_nms.db.settings_fields.shared import access_list_name


class f_network_definition(BaseModel):
    address: IPv4Address | IPv6Address | IPv4Network | IPv6Network
    comment: str = ""

    # Convert address to string.
    @field_validator("address", mode="after")
    @classmethod
    def validate_address(cls, v):
        return str(v)


class f_network_definition_include(BaseModel):
    name: str


class f_network_definition_reference(BaseModel):
    path: str
    strip_cidr: Optional[bool] = False

    @field_validator("path", mode="after")
    @classmethod
    def validate_jmespath(cls, v: str) -> str:
        try:
            jmespath.compile(v)
        except ParseError as e:
            raise ValueError(str(e))
        return v


class f_service_definition(BaseModel):
    port: int | str
    protocol: str


class f_service_definition_include(BaseModel):
    name: str


TermsListAdapter: TypeAdapter = TypeAdapter(TermsList)

TermsListAdapter.rebuild()


class f_access_list(BaseModel):
    comment: str = ""
    inet_families: List[Literal["ipv4", "ipv6"]] = ["ipv4"]
    header_map: Dict[str, str] = {}
    # Example header_map
    # {"ios": "{ACL_NAME} {INET_FAMILY} noverbose",
    # "eos": "ACL_NAME extended noverbose"}

    # Uses Aerleon TypedDict
    terms: TermsList

    @field_validator("inet_families", mode="after")
    @classmethod
    def unique_sorted_inet_families(cls, v: List[Literal["ipv4", "ipv6"]]) -> List[Literal["ipv4", "ipv6"]]:
        """Make sure inet_families are unique and sorted"""
        return sorted(set(v))

    @field_validator("header_map", mode="after")
    @classmethod
    def validate_header_map(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Make sure header_map only contains valid options"""
        valid_platforms = list(NAPALM_LIB_MAPPER.keys()) + list(AERLEON_LIB_MAPPER.keys())
        for k in v.keys():
            if k not in valid_platforms:
                raise ValueError(f"{k} must be a valid napalm or aerleon platform")

        return v

    @field_validator("terms", mode="after")
    def validate_term_names(cls, v):
        """
        All terms must have valid names
        Term name uniqueness is handled in f_root
        """
        for term in v:
            if "include" in term:
                # This is a PolicyInclude and is validated later in f_root.
                continue

            term_name = term.get("name")

            if not term_name:
                raise ValueError("Terms must have a name")

            # Invalid characters is a ValueError
            if not re.match(r"^[\w-]+$", term_name):
                raise ValueError(f"Invalid term name: {term_name}")

        return v

    @field_validator("terms", mode="after")
    @classmethod
    def validate_terms(cls, terms):
        if not terms:
            raise ValueError("Terms must be defined and cannot be empty")

        # Validate all terms regarding to the TypedDict
        TermsListAdapter.validate_python(terms)

        return terms


f_access_list.model_rebuild()


class f_access_lists(BaseModel):
    network_definitions: Dict[
        str, List[f_network_definition | f_network_definition_include | f_network_definition_reference]
    ] = {}
    service_definitions: Dict[str, List[f_service_definition | f_service_definition_include]] = {}
    access_lists: Dict[access_list_name, f_access_list] = {}

    @field_validator("access_lists", mode="after")
    @classmethod
    def validate_access_lists_includes(
        cls, access_lists: Dict[access_list_name, f_access_list]
    ) -> Dict[access_list_name, f_access_list]:
        """Raise an error if some term include is not pointing to a valid access_list"""
        acl_names = access_lists.keys()
        for access_list in access_lists.values():
            for term in access_list.terms:
                include_acl = term.get("include")
                if include_acl and include_acl not in acl_names:
                    raise ValueError(f"Included access-list: {include_acl} must be defined.")
        return access_lists

    @field_validator("access_lists", mode="after")
    @classmethod
    def validate_access_lists_included_terms(
        cls, access_lists: Dict[access_list_name, f_access_list]
    ) -> Dict[access_list_name, f_access_list]:
        """Validates an access-list + included access-lists have unique term-names"""
        for access_list in access_lists.values():
            all_term_names = [t.get("name") for t in access_list.terms if t.get("name")]
            for term in access_list.terms:
                include_acl = term.get("include")

                if include_acl and isinstance(include_acl, str):
                    all_term_names.extend([t.get("name") for t in access_lists[include_acl].terms if t.get("name")])

            if len(all_term_names) != len(set(all_term_names)):
                raise ValueError("All term names in an access-list + included access-lists must be unique.")
        return access_lists
