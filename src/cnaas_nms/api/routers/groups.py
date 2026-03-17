from typing import List, Optional

from fastapi import APIRouter, Depends

from cnaas_nms.api.dependencies import get_current_user
from cnaas_nms.api.response import CnaasJSONResponse, empty_result
from cnaas_nms.db.device import Device, DeviceState
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.settings import get_group, get_group_settings, get_groups

router = APIRouter(tags=["groups"])


def groups_populate(group_name: Optional[str] = None) -> dict:
    if group_name:
        tmpgroups: dict = {group_name: []}
    else:
        tmpgroups = {key: [] for key in get_groups()}
    with sqla_session() as session:
        devices: List[Device] = session.query(Device).all()
        for dev in devices:
            groups = get_groups(dev)
            for group in groups:
                if group in tmpgroups:
                    tmpgroups[group].append(dev.hostname)
    return tmpgroups


def groups_settings_populate(group_name: Optional[str] = None) -> dict:
    settings, _ = get_group_settings()

    if group_name:
        group_list = [group for group in settings.groups if group.name == group_name]
    else:
        group_list = settings.groups

    ret = {}
    for group in group_list:
        ret[group.name] = group.model_dump()
        del ret[group.name]["name"]

    return ret


def groups_osversion_populate(group_name: str):
    os_versions: dict = {}

    group = get_group(group_name)
    if not group:
        raise ValueError("Could not find group {}".format(group_name))

    with sqla_session() as session:
        devices: List[Device] = (
            session.query(Device).filter(Device.state == DeviceState.MANAGED).order_by(Device.hostname.asc()).all()
        )
        for dev in devices:
            if not dev.os_version:
                continue
            if group.matches(dev):
                if dev.os_version in os_versions:
                    os_versions[dev.os_version].append(dev.hostname)
                else:
                    os_versions[dev.os_version] = [dev.hostname]
    return {group_name: os_versions}


@router.get("/groups")
def get_groups_api(user: str = Depends(get_current_user)):
    """Get all groups."""
    result = {"groups": groups_populate(), "group_settings": groups_settings_populate()}
    return empty_result(status="success", data=result)


@router.get("/groups/{group_name}")
def get_group_by_name(group_name: str, user: str = Depends(get_current_user)):
    """Get a single group by name."""
    if group_name not in get_groups():
        return CnaasJSONResponse(
            status_code=404,
            content=empty_result(status="error", data="No such group found, or group is not valid"),
        )
    result = {
        "groups": groups_populate(group_name),
        "group_settings": groups_settings_populate(group_name),
    }
    return empty_result(status="success", data=result)


@router.get("/groups/{group_name}/os_version")
def get_group_os_version(group_name: str, user: str = Depends(get_current_user)):
    """Get OS version of all devices in a group."""
    try:
        group_os_versions = groups_osversion_populate(group_name)
    except ValueError as e:
        return CnaasJSONResponse(
            status_code=404,
            content=empty_result(
                status="error", data="Exception while getting group {}: {}".format(group_name, str(e))
            ),
        )
    except Exception as e:
        return CnaasJSONResponse(
            status_code=500,
            content=empty_result(
                status="error", data="Exception while getting group {}: {}".format(group_name, str(e))
            ),
        )
    result = {"groups": group_os_versions}
    return empty_result(status="success", data=result)
