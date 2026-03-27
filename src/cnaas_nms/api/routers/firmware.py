import json
from datetime import datetime
from typing import Any, Optional

import requests
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cnaas_nms.api.dependencies import get_current_user
from cnaas_nms.api.response import CnaasJSONResponse, empty_result
from cnaas_nms.app_settings import api_settings
from cnaas_nms.db.device import Device
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.settings import get_groups
from cnaas_nms.devicehandler.nornir_helper import cnaas_init, inventory_selector
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.tools.log import get_logger

logger = get_logger()

router = APIRouter(tags=["firmware"])


class FirmwareDownload(BaseModel):
    url: str
    checksum: Optional[dict[str, str]] = None
    sha1: Optional[str] = None
    verify_tls: bool
    filename: Optional[str] = None


class FirmwareUpgradecheck(BaseModel):
    group: str


@router.get("/firmware")
def get_firmwares(user: str = Depends(get_current_user)):
    """Get firmwares."""
    try:
        res = requests.get(api_settings.HTTPD_URL, verify=api_settings.VERIFY_TLS)
        json_data = json.loads(res.content)["data"]
    except Exception as e:
        logger.exception(f"Exception when getting files: {e}")
        return CnaasJSONResponse(status_code=404, content=empty_result(status="error", data="Could not get files"))
    return empty_result(status="success", data=json_data)


@router.post("/firmware")
def download_firmware(firmware_data: FirmwareDownload, user: str = Depends(get_current_user)):
    """Download new firmware."""
    kwargs: dict[str, Any] = {}

    if not firmware_data.checksum and not firmware_data.sha1:
        return CnaasJSONResponse(content=empty_result(status="error", data="Missing parameter checksum"))

    kwargs["url"] = firmware_data.url

    if firmware_data.sha1:
        kwargs["sha1"] = firmware_data.sha1
    else:
        kwargs["checksum"] = firmware_data.checksum

    kwargs["verify_tls"] = firmware_data.verify_tls

    scheduler: Scheduler = Scheduler()
    job_id = scheduler.add_onetime_job(
        "cnaas_nms.api.firmware:download_firmware_to_nms",
        when=1,
        scheduled_by=user,
        kwargs=kwargs,
    )
    res = empty_result(data="Scheduled job to download firmware")
    res["job_id"] = job_id

    return res


@router.get("/firmware/{filename}")
def get_firmware_image(filename: str, user: str = Depends(get_current_user)):
    """Get information about a single firmware."""
    try:
        res = requests.get(f"{api_settings.HTTPD_URL}/{filename}", verify=api_settings.VERIFY_TLS)
        json_data = json.loads(res.content)["data"]
    except Exception as e:
        logger.exception(f"Exception when getting file: {e}")
        return CnaasJSONResponse(status_code=404, content=empty_result(status="error", data="Could not get file"))
    return empty_result(status="success", data=json_data)


@router.delete("/firmware/{filename}")
def delete_firmware(filename: str, user: str = Depends(get_current_user)):
    """Remove firmware."""
    try:
        res = requests.delete(f"{api_settings.HTTPD_URL}/{filename}", verify=api_settings.VERIFY_TLS)
        json_data = json.loads(res.content)["data"]
    except Exception as e:
        logger.exception(f"Exception when deleting file: {e}")
        return CnaasJSONResponse(status_code=404, content=empty_result(status="error", data="Could not delete file"))
    return empty_result(status="success", data=json_data)


@router.post("/firmware/{filename}/set-default")
def set_default_firmware(filename: str, user: str = Depends(get_current_user)):
    """Set a firmware as the default image."""
    try:
        res = requests.post(f"{api_settings.HTTPD_URL}/{filename}/set-default", verify=api_settings.VERIFY_TLS)
        json_data = json.loads(res.content)["data"]
    except Exception as e:
        logger.exception(f"Exception when setting file as default: {e}")
        return CnaasJSONResponse(
            status_code=404, content=empty_result(status="error", data="Could not set file as default")
        )
    return empty_result(status="success", data=json_data)


@router.post("/firmware/upgrade")
def upgrade_firmware(json_data: dict[str, Any], user: str = Depends(get_current_user)):
    """Upgrade firmware on device."""
    kwargs: dict[str, Any] = {}
    seconds = 1
    date_format = "%Y-%m-%d %H:%M:%S"
    url = api_settings.FIRMWARE_URL

    if "url" not in json_data and url == "":
        return CnaasJSONResponse(
            content=empty_result(
                status="error", data='No external address configured for HTTPD, please specify one with "url"'
            )
        )

    if "url" not in json_data:
        kwargs["url"] = url
    else:
        if isinstance(json_data["url"], str):
            kwargs["url"] = json_data["url"]
        else:
            return CnaasJSONResponse(content=empty_result(status="error", data="url should be a string"))

    for bool_field in ["activate", "download", "reboot", "pre_flight", "post_flight", "staggered_upgrade"]:
        if bool_field in json_data:
            if isinstance(json_data[bool_field], bool):
                kwargs[bool_field] = json_data[bool_field]
            else:
                return CnaasJSONResponse(content=empty_result(status="error", data=f"{bool_field} should be a boolean"))

    if "post_waittime" in json_data:
        if isinstance(json_data["post_waittime"], int):
            kwargs["post_waittime"] = json_data["post_waittime"]
        else:
            return CnaasJSONResponse(content=empty_result(status="error", data="post_waittime should be an integer"))

    if "filename" in json_data:
        if isinstance(json_data["filename"], str):
            kwargs["filename"] = json_data["filename"]
        else:
            return CnaasJSONResponse(content=empty_result(status="error", data="filename should be a string"))

    total_count: Optional[int] = None
    nr = cnaas_init()

    if "hostname" in json_data:
        hostname = str(json_data["hostname"])
        if not Device.valid_hostname(hostname):
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data=f"Hostname '{hostname}' is not a valid hostname"),
            )
        _, total_count, _ = inventory_selector(nr, hostname=hostname)
        if total_count != 1:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(
                    status="error", data=f"Hostname '{hostname}' not found or is not a managed device"
                ),
            )
        kwargs["hostname"] = hostname
    elif "group" in json_data:
        group_name = str(json_data["group"])
        if group_name not in get_groups():
            return CnaasJSONResponse(
                content=empty_result(status="error", data="Could not find a group with name {}".format(group_name))
            )
        kwargs["group"] = group_name
        _, total_count, _ = inventory_selector(nr, group=group_name)
    else:
        return CnaasJSONResponse(
            status_code=400, content=empty_result(status="error", data="No devices to upgrade were specified")
        )

    if "comment" in json_data and isinstance(json_data["comment"], str):
        kwargs["job_comment"] = json_data["comment"]
    if "ticket_ref" in json_data and isinstance(json_data["ticket_ref"], str):
        kwargs["job_ticket_ref"] = json_data["ticket_ref"]

    if "start_at" in json_data:
        try:
            time_start = datetime.strptime(json_data["start_at"], date_format)
            time_now = datetime.utcnow()

            if time_start < time_now:
                return CnaasJSONResponse(content=empty_result(status="error", data="start_at must be in the future"))
            time_diff = time_start - time_now
            seconds = int(time_diff.total_seconds())
        except Exception as e:
            logger.exception(f"Exception when scheduling job: {e}")
            return CnaasJSONResponse(
                content=empty_result(status="error", data=f"Invalid date format, should be: {date_format}")
            )

    scheduler: Scheduler = Scheduler()
    job_id = scheduler.add_onetime_job(
        "cnaas_nms.devicehandler.firmware:device_upgrade",
        when=seconds,
        scheduled_by=user,
        kwargs=kwargs,
    )
    res = empty_result(data="Scheduled job to upgrade devices")
    res["job_id"] = job_id

    headers = {}
    if total_count:
        headers["X-Total-Count"] = str(total_count)
    return CnaasJSONResponse(content=res, headers=headers)


@router.post("/firmware/upgradecheck")
def firmware_upgradecheck(check_data: FirmwareUpgradecheck, user: str = Depends(get_current_user)):
    """Perform upgrade check on device group."""
    nr = cnaas_init()
    nr_filtered_group, dev_count, _ = inventory_selector(nr, group=check_data.group)

    device_hostname_list = list(nr_filtered_group.inventory.hosts.keys())

    with sqla_session() as session:
        upgrade_groups: list[list[str]] = []
        device_list: list[Device] = []

        for device in device_hostname_list:
            dev: Optional[Device] = session.query(Device).filter(Device.hostname == device).one_or_none()
            if not dev:
                raise Exception("Could not find device: {}".format(device))
            device_list.append(dev)

        try:
            from cnaas_nms.devicehandler.upgradeorder import determine_upgrade_order

            upgrade_device_groups: list[list[Device]] = determine_upgrade_order(session, device_list)
        except NotImplementedError as e:
            return CnaasJSONResponse(status_code=400, content=empty_result(status="error", data=str(e)))
        except Exception as e:
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result(status="error", data=f"Could not determine upgrade order: {str(e)}"),
            )
        if not upgrade_device_groups:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(
                    status="error", data="Could not determine upgrade order for the specified device group"
                ),
            )
        upgrade_groups = [[device.hostname for device in group] for group in upgrade_device_groups]

    ret = empty_result(
        status="success",
        data={"upgrade_groups": upgrade_groups, "device_count": dev_count, "steps": len(upgrade_groups)},
    )
    return CnaasJSONResponse(content=ret, headers={"X-Total-Count": str(dev_count)})
