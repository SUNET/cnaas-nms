from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError

from cnaas_nms.api.dependencies import get_current_user
from cnaas_nms.api.filtering import build_filter
from cnaas_nms.api.generic import parse_pydantic_error, update_sqla_object
from cnaas_nms.api.mgmtdomain import f_mgmtdomain
from cnaas_nms.api.response import CnaasJSONResponse, empty_result
from cnaas_nms.db.device import Device
from cnaas_nms.db.mgmtdomain import Mgmtdomain
from cnaas_nms.db.session import sqla_session
from cnaas_nms.devicehandler.sync_history import add_sync_event

router = APIRouter(tags=["mgmtdomains"])


class MgmtdomainCreate(BaseModel):
    device_a: str
    device_b: str
    vlan: int
    ipv4_gw: Optional[str] = None
    ipv6_gw: Optional[str] = None
    description: Optional[str] = None


@router.get("/mgmtdomains")
def get_mgmtdomains(request: Request, user: str = Depends(get_current_user)):
    """Get all management domains."""
    result = empty_result()
    result["data"] = {"mgmtdomains": []}
    args = dict(request.query_params)
    per_page = int(args.get("per_page", 50))
    page = int(args.get("page", 1))

    with sqla_session() as session:
        query = session.query(Mgmtdomain)
        try:
            query = build_filter(Mgmtdomain, query, args, per_page=per_page, page=page)
        except Exception as e:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data="Unable to filter mgmtdomains: {}".format(e)),
            )
        for instance in query:
            result["data"]["mgmtdomains"].append(instance.as_dict())
    return result


@router.post("/mgmtdomains")
def create_mgmtdomain(mgmtdomain_data: MgmtdomainCreate, user: str = Depends(get_current_user)):
    """Add management domain."""
    json_data = mgmtdomain_data.model_dump()
    data: dict[str, Any] = {}
    errors = []

    with sqla_session() as session:
        hostname_a = str(json_data["device_a"])
        if not Device.valid_hostname(hostname_a):
            errors.append(f"Invalid hostname for device_a: {hostname_a}")
        else:
            device_a: Optional[Device] = session.query(Device).filter(Device.hostname == hostname_a).one_or_none()
            if not device_a:
                errors.append(f"Device with hostname {hostname_a} not found")
            else:
                data["device_a"] = device_a

        hostname_b = str(json_data["device_b"])
        if not Device.valid_hostname(hostname_b):
            errors.append(f"Invalid hostname for device_b: {hostname_b}")
        else:
            device_b: Optional[Device] = session.query(Device).filter(Device.hostname == hostname_b).one_or_none()
            if not device_b:
                errors.append(f"Device with hostname {hostname_b} not found")
            else:
                data["device_b"] = device_b

        try:
            data = {**data, **f_mgmtdomain(**json_data).model_dump()}
        except ValidationError as e:
            errors += parse_pydantic_error(e, f_mgmtdomain, json_data)

        required_keys_1 = ["device_a", "device_b", "vlan", "ipv4_gw"]
        required_keys_2 = ["device_a", "device_b", "vlan", "ipv6_gw"]
        required_in_data = all(key in data for key in required_keys_1) or all(key in data for key in required_keys_2)
        required_in_json_data = all(key in json_data for key in required_keys_1) or all(
            key in json_data for key in required_keys_2
        )
        if required_in_data and required_in_json_data:
            new_mgmtd = Mgmtdomain()
            new_mgmtd.device_a = data["device_a"]
            new_mgmtd.device_b = data["device_b"]
            new_mgmtd.ipv4_gw = data["ipv4_gw"]
            new_mgmtd.ipv6_gw = data["ipv6_gw"]
            new_mgmtd.vlan = data["vlan"]
            try:
                session.add(new_mgmtd)
                session.flush()
            except IntegrityError as e:
                session.rollback()
                if "duplicate" in str(e) and e.orig:
                    return CnaasJSONResponse(
                        status_code=400,
                        content=empty_result("error", "Duplicate value: {}".format(e.orig.args[0])),
                    )
                else:
                    return CnaasJSONResponse(
                        status_code=400,
                        content=empty_result("error", "Integrity error: {}".format(e)),
                    )

            device_a.synchronized = False  # type: ignore[union-attr]
            add_sync_event(device_a.hostname, "mgmtdomain_created", user)  # type: ignore[union-attr]
            device_b.synchronized = False  # type: ignore[union-attr]
            add_sync_event(device_b.hostname, "mgmtdomain_created", user)  # type: ignore[union-attr]
            return empty_result(status="success", data={"added_mgmtdomain": new_mgmtd.as_dict()})
        else:
            errors.append(
                "Not all required inputs were found: {} OR {}".format(
                    ", ".join(required_keys_1), ", ".join(required_keys_2)
                )
            )
            return CnaasJSONResponse(status_code=400, content=empty_result("error", errors))


@router.get("/mgmtdomain/{mgmtdomain_id}")
def get_mgmtdomain_by_id(mgmtdomain_id: int, user: str = Depends(get_current_user)):
    """Get management domain by ID."""
    result = empty_result()
    result["data"] = {"mgmtdomains": []}
    with sqla_session() as session:
        instance = session.query(Mgmtdomain).filter(Mgmtdomain.id == mgmtdomain_id).one_or_none()
        if instance:
            result["data"]["mgmtdomains"].append(instance.as_dict())
        else:
            return CnaasJSONResponse(status_code=404, content=empty_result("error", "Management domain not found"))
    return result


@router.delete("/mgmtdomain/{mgmtdomain_id}")
def delete_mgmtdomain(mgmtdomain_id: int, user: str = Depends(get_current_user)):
    """Remove management domain."""
    with sqla_session() as session:
        instance: Optional[Mgmtdomain] = session.query(Mgmtdomain).filter(Mgmtdomain.id == mgmtdomain_id).one_or_none()
        if instance:
            instance.device_a.synchronized = False
            add_sync_event(instance.device_a.hostname, "mgmtdomain_deleted", user)
            instance.device_b.synchronized = False
            add_sync_event(instance.device_b.hostname, "mgmtdomain_deleted", user)
            session.delete(instance)
            session.commit()
            return empty_result(status="success", data={"deleted_mgmtdomain": instance.as_dict()})
        else:
            return CnaasJSONResponse(status_code=404, content=empty_result("error", "Management domain not found"))


@router.put("/mgmtdomain/{mgmtdomain_id}")
def update_mgmtdomain(mgmtdomain_id: int, json_data: dict[str, Any], user: str = Depends(get_current_user)):
    """Modify management domain."""
    errors = []
    try:
        f_mgmtdomain(**json_data).model_dump()
    except ValidationError as e:
        errors += parse_pydantic_error(e, f_mgmtdomain, json_data)

    if errors:
        return CnaasJSONResponse(status_code=400, content=empty_result("error", errors))

    with sqla_session() as session:
        instance: Optional[Mgmtdomain] = session.query(Mgmtdomain).filter(Mgmtdomain.id == mgmtdomain_id).one_or_none()
        if instance:
            changed: bool = update_sqla_object(instance, json_data)
            if changed:
                instance.device_a.synchronized = False
                add_sync_event(instance.device_a.hostname, "mgmtdomain_updated", user)
                instance.device_b.synchronized = False
                add_sync_event(instance.device_b.hostname, "mgmtdomain_updated", user)
                return empty_result(status="success", data={"updated_mgmtdomain": instance.as_dict()})
            else:
                return empty_result(status="success", data={"unchanged_mgmtdomain": instance.as_dict()})
        else:
            return CnaasJSONResponse(status_code=400, content=empty_result(status="error", data="mgmtdomain not found"))
