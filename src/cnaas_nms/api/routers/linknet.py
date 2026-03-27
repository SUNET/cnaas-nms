from ipaddress import IPv4Network
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ValidationError

from cnaas_nms.api.dependencies import get_current_user
from cnaas_nms.api.generic import parse_pydantic_error, update_sqla_object
from cnaas_nms.api.linknet import f_linknet
from cnaas_nms.api.response import CnaasJSONResponse, empty_result
from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.session import sqla_session
from cnaas_nms.devicehandler.sync_history import add_sync_event
from cnaas_nms.devicehandler.underlay import find_free_infra_linknet

router = APIRouter(tags=["linknets"])


class LinknetCreate(BaseModel):
    device_a: str
    device_b: str
    device_a_port: str
    device_b_port: str
    ipv4_network: Optional[str] = None


class LinknetDelete(BaseModel):
    id: int


def validate_hostname(hostname: str) -> None:
    if not Device.valid_hostname(hostname):
        raise ValueError("Invalid hostname: {}".format(hostname))
    with sqla_session() as session:
        dev: Optional[Device] = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            raise ValueError("Hostname {} not found in database".format(hostname))


@router.get("/linknets")
def get_linknets(user: str = Depends(get_current_user)):
    """Get all linknets."""
    result: dict[str, Any] = {"linknets": []}
    with sqla_session() as session:
        query = session.query(Linknet)
        for instance in query:
            result["linknets"].append(instance.as_dict())
    return empty_result(status="success", data=result)


@router.post("/linknets", status_code=201)
def create_linknet(linknet_data: LinknetCreate, user: str = Depends(get_current_user)):
    """Add a new linknet."""
    errors = []
    for device_arg in ["device_a", "device_b"]:
        try:
            validate_hostname(getattr(linknet_data, device_arg))
        except ValueError as e:
            errors.append("Bad parameter {}: {}".format(device_arg, e))

    new_prefix = None
    if linknet_data.ipv4_network:
        try:
            new_prefix = IPv4Network(linknet_data.ipv4_network)
        except Exception as e:
            errors.append("Invalid ipv4_network: {}".format(e))

    if errors:
        return CnaasJSONResponse(status_code=400, content=empty_result(status="error", data=errors))

    with sqla_session() as session:
        dev_a: Optional[Device] = session.query(Device).filter(Device.hostname == linknet_data.device_a).one_or_none()
        if not dev_a:
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result(status="error", data="Hostname '{}' not found".format(linknet_data.device_a)),
            )

        dev_b: Optional[Device] = session.query(Device).filter(Device.hostname == linknet_data.device_b).one_or_none()
        if not dev_b:
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result(status="error", data="Hostname '{}' not found".format(linknet_data.device_b)),
            )

        ip_linknet_devtypes = [DeviceType.CORE, DeviceType.DIST]
        if dev_a.device_type in ip_linknet_devtypes and dev_b.device_type in ip_linknet_devtypes:
            if not new_prefix:
                new_prefix = find_free_infra_linknet(session)
            if not new_prefix:
                return CnaasJSONResponse(
                    status_code=400,
                    content=empty_result(
                        status="error", data="Device types requires IP linknets, but no prefix could be found"
                    ),
                )

        try:
            new_linknet = Linknet.create_linknet(
                session,
                linknet_data.device_a,
                linknet_data.device_a_port,
                linknet_data.device_b,
                linknet_data.device_b_port,
                new_prefix,
            )
            session.add(new_linknet)
            session.commit()
            data = new_linknet.as_dict()
        except Exception as e:
            session.rollback()
            return CnaasJSONResponse(status_code=500, content=empty_result(status="error", data=str(e)))

    return empty_result(status="success", data=data)


@router.delete("/linknets")
def delete_linknet_by_body(linknet_delete: LinknetDelete, user: str = Depends(get_current_user)):
    """Remove linknet by ID (in request body)."""
    with sqla_session() as session:
        cur_linknet: Optional[Linknet] = session.query(Linknet).filter(Linknet.id == linknet_delete.id).one_or_none()
        if not cur_linknet:
            return CnaasJSONResponse(
                status_code=404, content=empty_result(status="error", data="No such linknet found in database")
            )
        cur_linknet.device_a.synchronized = False
        add_sync_event(cur_linknet.device_a.hostname, "linknet_deleted", user)
        cur_linknet.device_b.synchronized = False
        add_sync_event(cur_linknet.device_b.hostname, "linknet_deleted", user)
        session.delete(cur_linknet)
        session.commit()
        return empty_result(status="success", data={"deleted_linknet": cur_linknet.as_dict()})


@router.get("/linknet/{linknet_id}")
def get_linknet_by_id(linknet_id: int, user: str = Depends(get_current_user)):
    """Get a single linknet by ID."""
    result = empty_result()
    result["data"] = {"linknets": []}
    with sqla_session() as session:
        instance = session.query(Linknet).filter(Linknet.id == linknet_id).one_or_none()
        if instance:
            result["data"]["linknets"].append(instance.as_dict())
        else:
            return CnaasJSONResponse(status_code=404, content=empty_result("error", "Linknet not found"))
    return result


@router.delete("/linknet/{linknet_id}")
def delete_linknet_by_id(linknet_id: int, user: str = Depends(get_current_user)):
    """Remove a linknet by ID."""
    with sqla_session() as session:
        instance: Optional[Linknet] = session.query(Linknet).filter(Linknet.id == linknet_id).one_or_none()
        if instance:
            instance.device_a.synchronized = False
            add_sync_event(instance.device_a.hostname, "linknet_deleted", user)
            instance.device_b.synchronized = False
            add_sync_event(instance.device_b.hostname, "linknet_deleted", user)
            session.delete(instance)
            session.commit()
            return empty_result(status="success", data={"deleted_linknet": instance.as_dict()})
        else:
            return CnaasJSONResponse(
                status_code=404, content=empty_result("error", "No such linknet found in database")
            )


@router.put("/linknet/{linknet_id}")
def update_linknet(linknet_id: int, json_data: dict[str, Any], user: str = Depends(get_current_user)):
    """Update data on existing linknet."""
    errors = []
    for device_arg in ["device_a", "device_b"]:
        if device_arg in json_data:
            try:
                validate_hostname(json_data[device_arg])
            except ValueError as e:
                errors.append("Bad parameter {}: {}".format(device_arg, e))

    if errors:
        return CnaasJSONResponse(status_code=400, content=empty_result(status="error", data=errors))

    with sqla_session() as session:
        instance: Optional[Linknet] = session.query(Linknet).filter(Linknet.id == linknet_id).one_or_none()
        if instance:
            try:
                validate_data = {**instance.as_dict(), **json_data}
                f_linknet(**validate_data).model_dump()
            except ValidationError as e:
                errors += parse_pydantic_error(e, f_linknet, validate_data)
            if errors:
                return CnaasJSONResponse(status_code=400, content=empty_result(status="error", data=errors))

            changed: bool = update_sqla_object(instance, json_data)
            if changed:
                instance.device_a.synchronized = False
                add_sync_event(instance.device_a.hostname, "linknet_updated", user)
                instance.device_b.synchronized = False
                add_sync_event(instance.device_b.hostname, "linknet_updated", user)
                return empty_result(status="success", data={"updated_linknet": instance.as_dict()})
            else:
                return empty_result(status="success", data={"unchanged_linknet": instance.as_dict()})
        else:
            return CnaasJSONResponse(status_code=400, content=empty_result(status="error", data="linknet not found"))
