import datetime
from copy import deepcopy
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified

import cnaas_nms.devicehandler.get
import cnaas_nms.devicehandler.init_device
import cnaas_nms.devicehandler.sync_devices
import cnaas_nms.devicehandler.underlay
import cnaas_nms.devicehandler.update
from cnaas_nms.api.dependencies import get_current_user
from cnaas_nms.api.filtering import build_filter, pagination_headers
from cnaas_nms.api.generic import parse_pydantic_error
from cnaas_nms.api.models.stackmembers_model import StackmembersModel
from cnaas_nms.api.response import CnaasJSONResponse, empty_result
from cnaas_nms.app_settings import api_settings
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.interface import Interface
from cnaas_nms.db.job import InvalidJobError, Job, JobNotFoundError
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.settings import (
    AccessListGenerationError,
    SettingsSyntaxError,
    VlanConflictError,
    get_device_primary_groups,
    get_groups,
    get_settings,
    rebuild_settings_cache,
    update_device_primary_groups,
)
from cnaas_nms.db.stackmember import Stackmember
from cnaas_nms.devicehandler.nornir_helper import cnaas_init, inventory_selector
from cnaas_nms.devicehandler.sync_history import (
    NewSyncEventModel,
    SyncHistory,
    add_sync_event,
    get_sync_events,
    remove_sync_events,
)
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.tools.log import get_logger

logger = get_logger()

router = APIRouter(tags=["devices"])


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def device_data_postprocess(device_list: List[Device]) -> List[dict]:
    device_primary_group = get_device_primary_groups()
    ret: List[dict] = []
    for device in device_list:
        dev_dict = device.as_dict()
        if device.hostname in device_primary_group.keys():
            dev_dict["primary_group"] = device_primary_group[device.hostname]
        ret.append(dev_dict)
    return ret


def _is_name_change_allowed(device: Device, new_hostname: str) -> bool:
    if device.state != DeviceState.MANAGED:
        return True

    new_dev = deepcopy(device)
    new_dev.hostname = new_hostname
    old_settings, _ = get_settings(device)
    new_settings, _ = get_settings(new_dev)

    return old_settings == new_settings


def init_device_arg_check(device_id: int, json_data: dict) -> dict:
    parsed_args: dict[str, int | str | list[Any] | None] = {"device_id": device_id}
    if not isinstance(device_id, int):
        raise ValueError("'device_id' must be an integer")

    if "hostname" not in json_data:
        raise ValueError("POST data must include new 'hostname'")
    else:
        if not Device.valid_hostname(json_data["hostname"]):
            raise ValueError("Provided hostname is not valid")
        else:
            parsed_args["new_hostname"] = json_data["hostname"]

    if "device_type" not in json_data:
        raise ValueError("POST data must include 'device_type'")
    else:
        try:
            device_type = str(json_data["device_type"]).upper()
        except Exception:
            raise ValueError("'device_type' must be a string")

        if DeviceType.has_name(device_type):
            parsed_args["device_type"] = device_type
        else:
            raise ValueError("Invalid 'device_type' provided")

    if "mlag_peer_id" in json_data or "mlag_peer_hostname" in json_data:
        if "mlag_peer_id" not in json_data or "mlag_peer_hostname" not in json_data:
            raise ValueError("Both 'mlag_peer_id' and 'mlag_peer_hostname' must be specified")
        if not isinstance(json_data["mlag_peer_id"], int):
            raise ValueError("'mlag_peer_id' must be an integer")
        if not Device.valid_hostname(json_data["mlag_peer_hostname"]):
            raise ValueError("Provided 'mlag_peer_hostname' is not valid")
        parsed_args["mlag_peer_id"] = json_data["mlag_peer_id"]
        parsed_args["mlag_peer_new_hostname"] = json_data["mlag_peer_hostname"]

    if "neighbors" in json_data and json_data["neighbors"] is not None:
        if isinstance(json_data["neighbors"], list):
            for neighbor in json_data["neighbors"]:
                if not Device.valid_hostname(neighbor):
                    raise ValueError("Invalid hostname specified in neighbor list")
            parsed_args["neighbors"] = json_data["neighbors"]
        else:
            raise ValueError(
                "Neighbors must be specified as either a list of hostnames,an empty list, or not specified at all"
            )
    else:
        parsed_args["neighbors"] = None

    if "replace_hostname" in json_data and json_data["replace_hostname"] is not None:
        parsed_args["replace_hostname"] = json_data["replace_hostname"]

    return parsed_args


def parse_syncto_args(json_data: dict) -> dict:
    # default args
    kwargs: dict = {
        "dry_run": True,
        "auto_push": False,
        "force": False,
        "resync": False,
    }

    if "dry_run" in json_data and isinstance(json_data["dry_run"], bool) and not json_data["dry_run"]:
        kwargs["dry_run"] = False
    if "force" in json_data and isinstance(json_data["force"], bool):
        kwargs["force"] = json_data["force"]
    if "auto_push" in json_data and isinstance(json_data["auto_push"], bool):
        kwargs["auto_push"] = json_data["auto_push"]
    if "resync" in json_data and isinstance(json_data["resync"], bool):
        kwargs["resync"] = json_data["resync"]
    if "comment" in json_data and isinstance(json_data["comment"], str):
        kwargs["job_comment"] = json_data["comment"]
    if "ticket_ref" in json_data and isinstance(json_data["ticket_ref"], str):
        kwargs["job_ticket_ref"] = json_data["ticket_ref"]
    if "confirm_mode" in json_data and isinstance(json_data["confirm_mode"], int):
        kwargs["confirm_mode_override"] = json_data["confirm_mode"]

    return kwargs


def filter_job_dict(job_dict: dict, args: dict) -> dict:
    """Filter out parts of job result dict based on query string arguments."""
    filter_map = {"syncto": {"config": 1, "diff": 2}}
    filter_items = []
    if (
        not isinstance(job_dict, dict)
        or "result" not in job_dict
        or not isinstance(job_dict["result"], dict)
        or "devices" not in job_dict["result"]
        or "function_name" not in job_dict
        or not isinstance(job_dict["function_name"], str)
    ):
        return job_dict

    if job_dict["function_name"].startswith("sync_devices"):
        for arg, value in args.items():
            if arg == "filter_jobresult" and isinstance(value, str):
                for item in value.split(","):
                    if item in filter_map["syncto"].keys():
                        filter_items.append(filter_map["syncto"][item])
        for filter_item in sorted(filter_items, reverse=True):
            for hostname, value in job_dict["result"]["devices"].items():
                try:
                    del job_dict["result"]["devices"][hostname]["job_tasks"][filter_item]
                except KeyError:
                    pass
                except Exception as e:
                    logger.debug("job filter_response exception: {}".format(e))
    return job_dict


def format_stackmember_errors(errors: list) -> list:
    return_errors = []
    for error in errors:
        error_msg = error["msg"]
        if error["type"] != "value_error":
            error_msg = f"{error['loc'][2]}: {error_msg}"
        return_errors.append(error_msg)
    return return_errors


# ---------------------------------------------------------------------------
# 1. DeviceByIdApi  GET /device/{device_id}
# ---------------------------------------------------------------------------


@router.get("/device/{device_id}")
def get_device_by_id(device_id: int, user: str = Depends(get_current_user)):
    """Get a device from ID."""
    result = empty_result()
    result["data"] = {"devices": []}
    with sqla_session() as session:
        instance = session.query(Device).filter(Device.id == device_id).one_or_none()
        if instance:
            result["data"]["devices"] = device_data_postprocess([instance])
        else:
            return CnaasJSONResponse(status_code=404, content=empty_result("error", "Device not found"))
    return result


# ---------------------------------------------------------------------------
# 1. DeviceByIdApi  DELETE /device/{device_id}
# ---------------------------------------------------------------------------


@router.delete("/device/{device_id}")
def delete_device_by_id(
    device_id: int,
    json_data: Optional[dict[str, Any]] = None,
    user: str = Depends(get_current_user),
):
    """Delete device from ID."""
    if json_data and "factory_default" in json_data:
        if isinstance(json_data["factory_default"], bool) and json_data["factory_default"] is True:
            scheduler = Scheduler()
            job_id = scheduler.add_onetime_job(
                "cnaas_nms.devicehandler.erase:device_erase",
                when=1,
                scheduled_by=user,
                kwargs={"device_id": device_id},
            )
            res = empty_result(data="Scheduled job {} to factory default device".format(job_id))
            res["job_id"] = job_id
            return res
        elif not isinstance(json_data["factory_default"], bool):
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data="Argument factory_default must be boolean"),
            )

    with sqla_session() as session:
        dev: Optional[Device] = session.query(Device).filter(Device.id == device_id).one_or_none()
        if not dev:
            return CnaasJSONResponse(status_code=404, content=empty_result("error", "Device not found"))
        try:
            remove_sync_events(dev.hostname)
            for nei in dev.get_neighbors(session):
                nei.synchronized = False
                add_sync_event(nei.hostname, "neighbor_deleted", user)
        except Exception as e:
            logger.warning("Could not mark neighbor as unsync after deleting {}: {}".format(dev.hostname, e))
        try:
            session.delete(dev)
            session.commit()
        except IntegrityError as e:
            session.rollback()
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result(
                    status="error",
                    data="Could not remove device because existing references: {}".format(e),
                ),
            )
        except Exception as e:
            session.rollback()
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result(status="error", data="Could not remove device: {}".format(e)),
            )
        return empty_result(status="success", data={"deleted_device": dev.as_dict()})


# ---------------------------------------------------------------------------
# 1. DeviceByIdApi  PUT /device/{device_id}
# ---------------------------------------------------------------------------


@router.put("/device/{device_id}")
def update_device_by_id(
    device_id: int,
    json_data: dict[str, Any],
    user: str = Depends(get_current_user),
):
    """Modify device from ID."""
    with sqla_session() as session:
        dev: Optional[Device] = session.query(Device).filter(Device.id == device_id).one_or_none()
        if not dev:
            return CnaasJSONResponse(
                status_code=404,
                content=empty_result(status="error", data=f"No device with id {device_id}"),
            )

        dev_prev_state: DeviceState = dev.state

        current_hostname: str = dev.hostname
        new_hostname = json_data.get("hostname", current_hostname)
        is_name_change_request = current_hostname != new_hostname

        if is_name_change_request and not _is_name_change_allowed(dev, new_hostname):
            msg = (
                f"Configuration after name change for {current_hostname} would not be the same."
                f" Please check device specific configuration for {current_hostname} and {new_hostname}"
            )
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data=[msg]),
            )

        errors = dev.device_update(**json_data)
        if errors:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data=errors),
            )

        if is_name_change_request:
            try:
                # Rebuild settings caches to make sure group memberships are
                # updated after setting new hostname
                rebuild_settings_cache()

                # Mark linknet neighbors as unsynchronized
                linknets = (
                    session.query(Linknet)
                    .filter(or_(Linknet.device_a_id == device_id, Linknet.device_b_id == device_id))
                    .all()
                )

                neighbor_device_ids = set()
                for ln in linknets:
                    if ln.device_a_id == device_id:
                        neighbor_device_ids.add(ln.device_b_id)
                    else:
                        neighbor_device_ids.add(ln.device_a_id)

                for neigh_id in neighbor_device_ids:
                    neigh_dev = session.query(Device).filter(Device.id == neigh_id).one()
                    neigh_dev.synchronized = False
                    add_sync_event(neigh_dev.hostname, "linknet_neighbor_name_change", by=user)

                # Update neighbor interfaces
                interfaces = (
                    session.query(Interface).filter(Interface.data["neighbor"].astext == current_hostname).all()
                )
                for intf in interfaces:
                    intf.data["neighbor"] = new_hostname
                    flag_modified(intf, "data")

                    if intf.device_id not in neighbor_device_ids:
                        intf_dev = session.query(Device).filter(Device.id == intf.device_id).one()
                        intf_dev.synchronized = False
                        add_sync_event(intf_dev.hostname, "neighbor_name_change", by=user)

                dev.synchronized = False
                add_sync_event(new_hostname, "device_name_change", by=user)

                logger.info(
                    f"Hostname changed from '{current_hostname}' to '{new_hostname}': "
                    f"marked {len(neighbor_device_ids)} connected devices as unsynchronized, "
                    f"updated {len(interfaces)} interface neighbor fields"
                )

            except SettingsSyntaxError as e:
                msg = "Error in settings repo configuration: {}".format(e)
                logger.error(msg)
                session.rollback()
                return CnaasJSONResponse(
                    status_code=500,
                    content=empty_result(status="error", data=msg),
                )
            except VlanConflictError as e:
                msg = "VLAN conflict in repo configuration: {}".format(e)
                logger.error(msg)
                session.rollback()
                return CnaasJSONResponse(
                    status_code=500,
                    content=empty_result(status="error", data=msg),
                )
            except AccessListGenerationError as e:
                msg = str(e)
                logger.error(msg)
                session.rollback()
                return CnaasJSONResponse(
                    status_code=500,
                    content=empty_result(status="error", data=msg),
                )

        if "synchronized" in json_data and json_data["synchronized"]:
            remove_sync_events(dev.hostname)

        if "state" in json_data and json_data["state"].upper() == "UNMANAGED" and dev_prev_state == DeviceState.MANAGED:
            add_sync_event(dev.hostname, "was_unmanaged", by=user)

        session.commit()
        update_device_primary_groups()
        dev_dict = device_data_postprocess([dev])[0]
        return empty_result(status="success", data={"updated_device": dev_dict})


# ---------------------------------------------------------------------------
# 2. DeviceByHostnameApi  GET /device/{hostname}
# ---------------------------------------------------------------------------


@router.get("/device/{hostname}")
def get_device_by_hostname(hostname: str, user: str = Depends(get_current_user)):
    """Get a device from hostname."""
    result = empty_result()
    result["data"] = {"devices": []}
    with sqla_session() as session:
        instance = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if instance:
            result["data"]["devices"] = device_data_postprocess([instance])
        else:
            return CnaasJSONResponse(status_code=404, content=empty_result("error", "Device not found"))
    return result


# ---------------------------------------------------------------------------
# 3. DeviceApi  POST /devices  (add new device)
# ---------------------------------------------------------------------------


@router.post("/devices")
def add_device(json_data: dict[str, Any], user: str = Depends(get_current_user)):
    """Add a device."""
    supported_platforms = ["eos", "junos", "ios", "iosxr", "nxos", "nxos_ssh"]
    data: dict = {}
    errors: list = []
    data, errors = Device.validate(**json_data)
    if errors != []:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data=errors),
        )
    with sqla_session() as session:
        instance: Optional[Device] = session.query(Device).filter(Device.hostname == data["hostname"]).one_or_none()
        if instance:
            errors.append("Device already exists")
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data=errors),
            )
        if "platform" not in data or data["platform"] not in supported_platforms:
            errors.append(
                "Device platform not specified or not known (must be any of: {})".format(", ".join(supported_platforms))
            )
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data=errors),
            )
        if data["device_type"] in ["DIST", "CORE"]:
            if "management_ip" not in data or not data["management_ip"]:
                data["management_ip"] = cnaas_nms.devicehandler.underlay.find_free_mgmt_lo_ip(session)
            if "infra_ip" not in data or not data["infra_ip"]:
                data["infra_ip"] = cnaas_nms.devicehandler.underlay.find_free_infra_ip(session)
        new_device = Device.device_create(**data)
        session.add(new_device)
        session.flush()
        update_device_primary_groups()
        dev_dict = device_data_postprocess([new_device])[0]
        return empty_result(status="success", data={"added_device": dev_dict})


# ---------------------------------------------------------------------------
# 4. DevicesApi  GET /devices  (list with filtering/pagination)
# ---------------------------------------------------------------------------


@router.get("/devices")
def get_devices(request: Request, user: str = Depends(get_current_user)):
    """Get all devices."""
    logger.info("started get devices")
    device_list: List[Device] = []
    total_count = 0
    args = dict(request.query_params)

    per_page = int(args.get("per_page", 50))
    page = int(args.get("page", 1))

    with sqla_session() as session:
        query = session.query(Device, func.count(Device.id).over().label("total"))
        try:
            query = build_filter(Device, query, args, per_page=per_page, page=page)
        except Exception as e:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data="Unable to filter devices: {}".format(e)),
            )
        for instance in query:
            device_list.append(instance.Device)
            total_count = instance.total
        data = {"devices": device_data_postprocess(device_list)}

    headers = pagination_headers(
        total_count, args, per_page=per_page, page=page, base_url=str(request.base_url) + "api/v1.0/devices"
    )
    return CnaasJSONResponse(
        content=empty_result(status="success", data=data),
        headers=headers,
    )


# ---------------------------------------------------------------------------
# 5. DeviceInitApi  POST /device_init/{device_id}
# ---------------------------------------------------------------------------


@router.post("/device_init/{device_id}")
def init_device(device_id: int, json_data: dict[str, Any], user: str = Depends(get_current_user)):
    """Init a device."""
    try:
        job_kwargs = init_device_arg_check(device_id, json_data)
    except ValueError as e:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data=str(e)),
        )

    # If device init is already in progress, reschedule a new step2 (connectivity check)
    # instead of trying to restart initialization
    with sqla_session() as session:
        dev: Optional[Device] = session.query(Device).filter(Device.id == device_id).one_or_none()
        if dev and dev.state == DeviceState.INIT and dev.management_ip and dev.device_type is not DeviceType.UNKNOWN:
            scheduler = Scheduler()
            job_id = scheduler.add_onetime_job(
                "cnaas_nms.devicehandler.init_device:init_device_step2",
                when=1,
                scheduled_by=user,
                kwargs={"device_id": device_id, "iteration": 1},
            )

            logger.info("Re-scheduled init step 2 for {} as job # {}".format(device_id, job_id))
            res = empty_result(data=f"Re-scheduled init step 2 for device_id {device_id}")
            res["job_id"] = job_id
            return res

    if job_kwargs["device_type"] == DeviceType.ACCESS.name:
        del job_kwargs["device_type"]
        del job_kwargs["neighbors"]
        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            "cnaas_nms.devicehandler.init_device:init_access_device_step1",
            when=1,
            scheduled_by=user,
            kwargs=job_kwargs,
        )
    elif job_kwargs["device_type"] in [DeviceType.CORE.name, DeviceType.DIST.name]:
        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            "cnaas_nms.devicehandler.init_device:init_fabric_device_step1",
            when=1,
            scheduled_by=user,
            kwargs=job_kwargs,
        )
    else:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="Unsupported 'device_type' provided"),
        )

    res = empty_result(data=f"Scheduled job to initialize device_id {str(device_id)}")
    res["job_id"] = job_id

    return res


# ---------------------------------------------------------------------------
# 6. DeviceInitCheckApi  POST /device_initcheck/{device_id}
# ---------------------------------------------------------------------------


@router.post("/device_initcheck/{device_id}")
def initcheck_device(device_id: int, json_data: dict[str, Any], user: str = Depends(get_current_user)):
    """Perform init check on a device."""
    ret: dict[str, Any] = {}
    linknets_all: list = []
    mlag_peer_dev: Optional[Device]
    try:
        parsed_args = init_device_arg_check(device_id, json_data)
        target_devtype = DeviceType[parsed_args["device_type"]]
        target_hostname = parsed_args["new_hostname"]
        mlag_peer_target_hostname: Optional[str] = None
        mlag_peer_id: Optional[int] = None
        mlag_peer_dev = None
        if "mlag_peer_id" in parsed_args and "mlag_peer_new_hostname" in parsed_args:
            mlag_peer_target_hostname = parsed_args["mlag_peer_new_hostname"]
            mlag_peer_id = parsed_args["mlag_peer_id"]
    except ValueError as e:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="Error parsing arguments: {}".format(e)),
        )

    with sqla_session() as session:
        try:
            dev: Device = cnaas_nms.devicehandler.init_device.pre_init_checks(session, device_id)
            linknets_all = dev.get_linknets_as_dict(session)
        except ValueError as e:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data="ValueError in pre_init_checks: {}".format(e)),
            )
        except Exception as e:
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result(status="error", data="Exception in pre_init_checks: {}".format(e)),
            )

        if mlag_peer_id:
            try:
                mlag_peer_dev = cnaas_nms.devicehandler.init_device.pre_init_checks(session, mlag_peer_id)
                linknets_all += mlag_peer_dev.get_linknets_as_dict(session)
            except ValueError as e:
                return CnaasJSONResponse(
                    status_code=400,
                    content=empty_result(status="error", data="ValueError in pre_init_checks: {}".format(e)),
                )
            except Exception as e:
                return CnaasJSONResponse(
                    status_code=500,
                    content=empty_result(status="error", data="Exception in pre_init_checks: {}".format(e)),
                )

        try:
            linknets_all += cnaas_nms.devicehandler.update.update_linknets(
                session,
                hostname=dev.hostname,
                devtype=target_devtype,
                ztp_hostname=target_hostname,
                mlag_peer_dev=mlag_peer_dev,
                dry_run=True,
            )
            if mlag_peer_dev:
                linknets_all += cnaas_nms.devicehandler.update.update_linknets(
                    session,
                    hostname=mlag_peer_dev.hostname,
                    devtype=target_devtype,
                    ztp_hostname=mlag_peer_target_hostname,
                    mlag_peer_dev=dev,
                    dry_run=True,
                )
            ret["linknets"] = Linknet.deduplicate_linknet_dicts(linknets_all)
            ret["linknets_compatible"] = True
        except ValueError as e:
            ret["linknets_compatible"] = False
            ret["linknets_error"] = str(e)
        except Exception as e:
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result(status="error", data="Exception in update_linknets: {}".format(e)),
            )

        try:
            if "linknets" in ret and ret["linknets"]:
                try:
                    ret["neighbors"] = cnaas_nms.devicehandler.init_device.pre_init_check_neighbors(
                        session, dev, target_devtype, ret["linknets"], parsed_args["neighbors"], mlag_peer_dev
                    )
                    ret["neighbors_compatible"] = True
                except cnaas_nms.devicehandler.init_device.InitVerificationError as e:
                    ret["neighbors_compatible"] = False
                    ret["neighbors_error"] = str(e)
            else:
                ret["neighbors_compatible"] = False
                ret["neighbors_error"] = "No linknets found"
        except (ValueError, cnaas_nms.devicehandler.init_device.InitVerificationError) as e:
            ret["neighbors_compatible"] = False
            ret["neighbors_error"] = str(e)
        except Exception as e:
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result(
                    status="error",
                    data="Exception in pre_init_check_neighbors: {}".format(e),
                ),
            )

        if mlag_peer_dev:
            try:
                ret["mlag_compatible"] = mlag_peer_dev.hostname in ret["neighbors"]
            except Exception:
                ret["mlag_compatible"] = False

    ret["parsed_args"] = parsed_args
    if mlag_peer_id and not ret["mlag_compatible"]:
        ret["compatible"] = False
    elif ret["linknets_compatible"] and ret["neighbors_compatible"]:
        ret["compatible"] = True
    else:
        ret["compatible"] = False
    return empty_result(data=ret)


# ---------------------------------------------------------------------------
# 7. DeviceDiscoverApi  POST /device_discover
# ---------------------------------------------------------------------------


@router.post("/device_discover")
def discover_device(json_data: dict[str, Any], user: str = Depends(get_current_user)):
    """Discover device."""
    if "ztp_mac" not in json_data:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="POST data must include 'ztp_mac'"),
        )
    if "dhcp_ip" not in json_data:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="POST data must include 'dhcp_ip'"),
        )
    ztp_mac = json_data["ztp_mac"]
    dhcp_ip = json_data["dhcp_ip"]

    job_id = cnaas_nms.devicehandler.init_device.schedule_discover_device(
        ztp_mac=ztp_mac, dhcp_ip=dhcp_ip, iteration=1, scheduled_by=user
    )

    logger.debug(f"Discover device for ztp_mac {ztp_mac} scheduled as ID {job_id}")

    res = empty_result(data=f"Scheduled job to discover device for ztp_mac {ztp_mac}")
    res["job_id"] = job_id

    return res


# ---------------------------------------------------------------------------
# 8. DeviceSyncApi  POST /device_syncto
# ---------------------------------------------------------------------------


@router.post("/device_syncto")
def sync_devices(json_data: dict[str, Any], user: str = Depends(get_current_user)):
    """Start sync of device(s)."""
    kwargs = parse_syncto_args(json_data)

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
                    status="error",
                    data=f"Hostname '{hostname}' not found or is not a managed device",
                ),
            )
        kwargs["hostnames"] = [hostname]
        what = hostname
    elif "device_type" in json_data:
        devtype_str = str(json_data["device_type"]).upper()
        if DeviceType.has_name(devtype_str):
            kwargs["device_type"] = devtype_str
        else:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(
                    status="error",
                    data=f"Invalid device type '{json_data['device_type']}' specified",
                ),
            )
        what = f"{json_data['device_type']} devices"
        _, total_count, _ = inventory_selector(nr, resync=kwargs["resync"], device_type=devtype_str)
    elif "group" in json_data:
        group_name = str(json_data["group"])
        if group_name not in get_groups():
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data="Could not find a group with name {}".format(group_name)),
            )
        kwargs["group"] = group_name
        what = "group {}".format(group_name)
        _, total_count, _ = inventory_selector(nr, resync=kwargs["resync"], group=group_name)
    elif "all" in json_data and isinstance(json_data["all"], bool) and json_data["all"]:
        what = "all devices"
        _, total_count, _ = inventory_selector(nr, resync=kwargs["resync"])
    else:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="No devices to synchronize were specified"),
        )

    scheduler = Scheduler()
    job_id = scheduler.add_onetime_job(
        "cnaas_nms.devicehandler.sync_devices:sync_devices",
        when=1,
        scheduled_by=user,
        kwargs=kwargs,
    )

    res = empty_result(data=f"Scheduled job to synchronize {what}")
    res["job_id"] = job_id

    headers: dict[str, str] = {}
    if total_count:
        headers["X-Total-Count"] = str(total_count)
    return CnaasJSONResponse(content=res, headers=headers)


# ---------------------------------------------------------------------------
# 9. DeviceSyncHostnameApi  POST /device_syncto/{hostname}
# ---------------------------------------------------------------------------


@router.post("/device_syncto/{hostname}")
def sync_device_by_hostname(
    hostname: str,
    json_data: dict[str, Any],
    user: str = Depends(get_current_user),
):
    """Start sync of device by hostname."""
    kwargs = parse_syncto_args(json_data)

    total_count: Optional[int] = None
    nr = cnaas_init()

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
                status="error",
                data=f"Hostname '{hostname}' not found or is not a managed device",
            ),
        )
    kwargs["hostnames"] = [hostname]
    what = hostname

    scheduler = Scheduler()
    job_id = scheduler.add_onetime_job(
        "cnaas_nms.devicehandler.sync_devices:sync_devices",
        when=1,
        scheduled_by=user,
        kwargs=kwargs,
    )
    res = empty_result(data=f"Scheduled job to synchronize {what}")
    res["job_id"] = job_id

    headers: dict[str, str] = {}
    if total_count:
        headers["X-Total-Count"] = str(total_count)
    return CnaasJSONResponse(content=res, headers=headers)


# ---------------------------------------------------------------------------
# 10. DeviceUpdateFactsApi  POST /device_update_facts
# ---------------------------------------------------------------------------


@router.post("/device_update_facts")
def update_facts(json_data: dict[str, Any], user: str = Depends(get_current_user)):
    """Start update facts of device(s)."""
    kwargs: dict = {}

    total_count: Optional[int] = None

    if "hostname" in json_data:
        hostname = str(json_data["hostname"])
        if not Device.valid_hostname(hostname):
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data=f"Hostname '{hostname}' is not a valid hostname"),
            )
        with sqla_session() as session:
            dev: Optional[Device] = session.query(Device).filter(Device.hostname == hostname).one_or_none()
            if not dev or (dev.state != DeviceState.MANAGED and dev.state != DeviceState.UNMANAGED):
                return CnaasJSONResponse(
                    status_code=400,
                    content=empty_result(
                        status="error",
                        data=f"Hostname '{hostname}' not found or is in invalid state",
                    ),
                )
        kwargs["hostname"] = hostname
        total_count = 1
    else:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="No target to be updated was specified"),
        )

    scheduler = Scheduler()
    job_id = scheduler.add_onetime_job(
        "cnaas_nms.devicehandler.update:update_facts",
        when=1,
        scheduled_by=user,
        kwargs=kwargs,
    )

    res = empty_result(data=f"Scheduled job to update facts for {hostname}")
    res["job_id"] = job_id

    headers: dict[str, str] = {}
    if total_count:
        headers["X-Total-Count"] = str(total_count)
    return CnaasJSONResponse(content=res, headers=headers)


# ---------------------------------------------------------------------------
# 11. DeviceUpdateInterfacesApi  POST /device_update_interfaces
# ---------------------------------------------------------------------------


@router.post("/device_update_interfaces")
def update_interfaces(json_data: dict[str, Any], user: str = Depends(get_current_user)):
    """Update/scan interfaces of device."""
    kwargs: dict = {"replace": False, "delete_all": False, "mlag_peer_hostname": None}

    total_count: Optional[int] = None

    if "hostname" in json_data:
        hostname = str(json_data["hostname"])
        if not Device.valid_hostname(hostname):
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data=f"Hostname '{hostname}' is not a valid hostname"),
            )
        with sqla_session() as session:
            dev: Optional[Device] = session.query(Device).filter(Device.hostname == hostname).one_or_none()
            if not dev or (dev.state != DeviceState.MANAGED and dev.state != DeviceState.UNMANAGED):
                return CnaasJSONResponse(
                    status_code=400,
                    content=empty_result(
                        status="error",
                        data=f"Hostname '{hostname}' not found or is in invalid state",
                    ),
                )
            if dev.device_type != DeviceType.ACCESS:
                return CnaasJSONResponse(
                    status_code=400,
                    content=empty_result(
                        status="error",
                        data="Only devices of type ACCESS has interface database to update",
                    ),
                )
        kwargs["hostname"] = hostname
        total_count = 1
    else:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="No target to be updated was specified"),
        )

    if "mlag_peer_hostname" in json_data:
        mlag_peer_hostname = str(json_data["mlag_peer_hostname"])
        if not Device.valid_hostname(mlag_peer_hostname):
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(
                    status="error",
                    data=f"Hostname '{mlag_peer_hostname}' is not a valid hostname",
                ),
            )
        with sqla_session() as session:
            dev = session.query(Device).filter(Device.hostname == mlag_peer_hostname).one_or_none()
            if not dev or (dev.state != DeviceState.MANAGED and dev.state != DeviceState.UNMANAGED):
                return CnaasJSONResponse(
                    status_code=400,
                    content=empty_result(
                        status="error",
                        data=f"Hostname '{mlag_peer_hostname}' not found or is in invalid state",
                    ),
                )
            if dev.device_type != DeviceType.ACCESS:
                return CnaasJSONResponse(
                    status_code=400,
                    content=empty_result(
                        status="error",
                        data="Only devices of type ACCESS has interface database to update",
                    ),
                )
        kwargs["mlag_peer_hostname"] = mlag_peer_hostname

    if "replace" in json_data and isinstance(json_data["replace"], bool) and json_data["replace"]:
        kwargs["replace"] = True

    if "delete_all" in json_data and isinstance(json_data["delete_all"], bool) and json_data["delete_all"]:
        kwargs["delete_all"] = True

    scheduler = Scheduler()
    job_id = scheduler.add_onetime_job(
        "cnaas_nms.devicehandler.update:update_interfacedb",
        when=1,
        scheduled_by=user,
        kwargs=kwargs,
    )

    res = empty_result(data=f"Scheduled job to update interfaces for {hostname}")
    res["job_id"] = job_id

    headers: dict[str, str] = {}
    if total_count:
        headers["X-Total-Count"] = str(total_count)
    return CnaasJSONResponse(content=res, headers=headers)


# ---------------------------------------------------------------------------
# 12. DeviceGenerateConfigApi  GET /device/{hostname}/generate_config
# ---------------------------------------------------------------------------


@router.get("/device/{hostname}/generate_config")
def generate_config(hostname: str, user: str = Depends(get_current_user)):
    """Get device configuration."""
    result = empty_result()
    result["data"] = {"config": None}
    if not Device.valid_hostname(hostname):
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="Invalid hostname specified"),
        )

    try:
        config, template_vars = cnaas_nms.devicehandler.sync_devices.generate_only(hostname)
        template_vars["host"] = hostname
        data = {
            "hostname": hostname,
            "generated_config": config,
            "available_variables": template_vars,
        }

        result["data"]["config"] = data

    except Exception as e:
        logger.exception(f"Exception while generating config for device {hostname}")
        return CnaasJSONResponse(
            status_code=500,
            content=empty_result(
                status="error",
                data="Exception while generating config for device {}: {} {}".format(hostname, type(e), str(e)),
            ),
        )

    return result


# ---------------------------------------------------------------------------
# 13. DeviceRunningConfigApi  GET /device/{hostname}/running_config
# ---------------------------------------------------------------------------


@router.get("/device/{hostname}/running_config")
def get_running_config(hostname: str, request: Request, user: str = Depends(get_current_user)):
    """Get running configuration from device."""
    args = dict(request.query_params)
    result = empty_result()
    result["data"] = {"config": None}
    if not Device.valid_hostname(hostname):
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="Invalid hostname specified"),
        )

    with sqla_session() as session:
        dev: Optional[Device] = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            return CnaasJSONResponse(status_code=404, content=empty_result("error", "Device not found"))

        try:
            if "interface" in args:
                running_config = cnaas_nms.devicehandler.get.get_running_config_interface(
                    session, hostname, args["interface"]
                )
            else:
                running_config = cnaas_nms.devicehandler.get.get_running_config(hostname)
        except Exception as e:
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result("error", "Exception: {}".format(str(e))),
            )

    result["data"]["config"] = running_config
    return result


# ---------------------------------------------------------------------------
# 14. DeviceLldpNeighborsApi  GET /device/{hostname}/lldp_neighbors
# ---------------------------------------------------------------------------


@router.get("/device/{hostname}/lldp_neighbors")
def get_lldp_neighbors(hostname: str, user: str = Depends(get_current_user)):
    """Get LLDP neighbors for device."""
    result = empty_result()
    result["data"] = {"lldp_neighbors": None}
    if not Device.valid_hostname(hostname):
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="Invalid hostname specified"),
        )
    try:
        lldp_result = cnaas_nms.devicehandler.get.get_neighbors(hostname)[hostname][0]
        if lldp_result.failed:
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result(status="error", data="Failed to get LLDP neighbors"),
            )
        lldp_data = lldp_result.result["lldp_neighbors"]
    except Exception as e:
        return CnaasJSONResponse(
            status_code=500,
            content=empty_result(status="error", data="Exception: {}".format(str(e))),
        )
    result["data"]["lldp_neighbors"] = lldp_data
    return result


# ---------------------------------------------------------------------------
# 15. DeviceLldpNeighborsDetailApi  GET /device/{hostname}/lldp_neighbors_detail
# ---------------------------------------------------------------------------


@router.get("/device/{hostname}/lldp_neighbors_detail")
def get_lldp_neighbors_detail(hostname: str, user: str = Depends(get_current_user)):
    """Get detailed LLDP neighbors for device."""
    result = empty_result()
    result["data"] = {"lldp_neighbors_detail": None}
    if not Device.valid_hostname(hostname):
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="Invalid hostname specified"),
        )
    try:
        lldp_result = cnaas_nms.devicehandler.get.get_neighbors(hostname, details=True)[hostname][0]
        if lldp_result.failed:
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result(status="error", data="Failed to get LLDP neighbors"),
            )
        lldp_data = lldp_result.result["lldp_neighbors_detail"]
    except Exception as e:
        return CnaasJSONResponse(
            status_code=500,
            content=empty_result(status="error", data="Exception: {}".format(str(e))),
        )
    result["data"]["lldp_neighbors_detail"] = lldp_data
    return result


# ---------------------------------------------------------------------------
# 16. DevicePreviousConfigApi  GET /device/{hostname}/previous_config
# ---------------------------------------------------------------------------


@router.get("/device/{hostname}/previous_config")
def get_previous_config(hostname: str, request: Request, user: str = Depends(get_current_user)):
    """Get previous configuration for device."""
    args = dict(request.query_params)
    result = empty_result()
    result["data"] = {"config": None}
    if not Device.valid_hostname(hostname):
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="Invalid hostname specified"),
        )

    kwargs: dict[str, Any] = {}
    if "job_id" in args:
        try:
            kwargs["job_id"] = int(args["job_id"])
        except Exception:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result("error", "job_id must be an integer"),
            )
    elif "previous" in args:
        try:
            kwargs["previous"] = int(args["previous"])
        except Exception:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result("error", "previous must be an integer"),
            )
    elif "before" in args:
        try:
            kwargs["before"] = datetime.datetime.fromisoformat(args["before"])
        except Exception:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result("error", "before must be a valid ISO format date time string"),
            )

    with sqla_session() as session:
        try:
            result["data"] = Job.get_previous_config(session, hostname, **kwargs)
        except JobNotFoundError as e:
            return CnaasJSONResponse(status_code=404, content=empty_result("error", str(e)))
        except InvalidJobError as e:
            return CnaasJSONResponse(status_code=500, content=empty_result("error", str(e)))
        except Exception as e:
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result("error", "Unhandled exception: {}".format(e)),
            )

    return result


# ---------------------------------------------------------------------------
# 17. DeviceApplyConfigApi  POST /device/{hostname}/apply_config
# ---------------------------------------------------------------------------


@router.post("/device/{hostname}/apply_config")
def apply_config(hostname: str, json_data: dict[str, Any], user: str = Depends(get_current_user)):
    """Apply exact specified configuration to device without using templates."""
    apply_kwargs: dict[str, Any] = {"hostname": hostname}
    allow_live_run = api_settings.ALLOW_APPLY_CONFIG_LIVERUN
    if not Device.valid_hostname(hostname):
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="Invalid hostname specified"),
        )

    if "full_config" not in json_data:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result("error", "full_config must be specified"),
        )

    if "dry_run" in json_data and isinstance(json_data["dry_run"], bool) and not json_data["dry_run"]:
        if allow_live_run:
            apply_kwargs["dry_run"] = False
        else:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result("error", "Apply config live_run is not allowed"),
            )
    else:
        apply_kwargs["dry_run"] = True

    apply_kwargs["config"] = json_data["full_config"]

    scheduler = Scheduler()
    job_id = scheduler.add_onetime_job(
        "cnaas_nms.devicehandler.sync_devices:apply_config",
        when=1,
        scheduled_by=user,
        kwargs=apply_kwargs,
    )

    res = empty_result(data=f"Scheduled job to apply config {hostname}")
    res["job_id"] = job_id

    return res


# ---------------------------------------------------------------------------
# 18. DeviceRestoreApi  POST /device/{hostname}/restore
# ---------------------------------------------------------------------------


@router.post("/device/{hostname}/restore")
def restore_config(hostname: str, json_data: dict[str, Any], user: str = Depends(get_current_user)):
    """Restore configuration to previous version."""
    apply_kwargs: dict[str, Any] = {"hostname": hostname}
    config = None
    if not Device.valid_hostname(hostname):
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="Invalid hostname specified"),
        )

    if "job_id" in json_data:
        try:
            job_id = int(json_data["job_id"])
        except Exception:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result("error", "job_id must be an integer"),
            )
    else:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result("error", "job_id must be specified"),
        )

    with sqla_session() as session:
        try:
            prev_config_result = Job.get_previous_config(session, hostname, job_id=job_id)
            failed = prev_config_result["failed"]
            if not failed and "config" in prev_config_result:
                config = prev_config_result["config"]
        except JobNotFoundError as e:
            return CnaasJSONResponse(status_code=404, content=empty_result("error", str(e)))
        except InvalidJobError as e:
            return CnaasJSONResponse(status_code=500, content=empty_result("error", str(e)))
        except Exception as e:
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result("error", "Unhandled exception: {}".format(e)),
            )

    if failed:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result("error", "The specified job_id has a failed status"),
        )

    if not config:
        return CnaasJSONResponse(
            status_code=500,
            content=empty_result("error", "No config found in this job"),
        )

    if "dry_run" in json_data and isinstance(json_data["dry_run"], bool) and not json_data["dry_run"]:
        apply_kwargs["dry_run"] = False
    else:
        apply_kwargs["dry_run"] = True

    apply_kwargs["config"] = config

    scheduler = Scheduler()
    job_id = scheduler.add_onetime_job(
        "cnaas_nms.devicehandler.sync_devices:apply_config",
        when=1,
        scheduled_by=user,
        kwargs=apply_kwargs,
    )

    res = empty_result(data=f"Scheduled job to restore {hostname}")
    res["job_id"] = job_id

    return res


# ---------------------------------------------------------------------------
# 19. DeviceCertApi  POST /device_cert
# ---------------------------------------------------------------------------


@router.post("/device_cert")
def renew_cert(json_data: dict[str, Any], user: str = Depends(get_current_user)):
    """Execute certificate related actions on device."""
    kwargs: dict = {}

    if "action" in json_data and isinstance(json_data["action"], str):
        action = json_data["action"].upper()
    else:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="Required field 'action' was not specified"),
        )

    if "comment" in json_data and isinstance(json_data["comment"], str):
        kwargs["job_comment"] = json_data["comment"]
    if "ticket_ref" in json_data and isinstance(json_data["ticket_ref"], str):
        kwargs["job_ticket_ref"] = json_data["ticket_ref"]

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
                    status="error",
                    data=f"Hostname '{hostname}' not found or is not a managed device",
                ),
            )
        kwargs["hostname"] = hostname
    elif "group" in json_data:
        group_name = str(json_data["group"])
        if group_name not in get_groups():
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result(status="error", data="Could not find a group with name {}".format(group_name)),
            )
        kwargs["group"] = group_name
        _, total_count, _ = inventory_selector(nr, group=group_name)
    else:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="No devices were specified"),
        )

    if action == "RENEW":
        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            "cnaas_nms.devicehandler.cert:renew_cert",
            when=1,
            scheduled_by=user,
            kwargs=kwargs,
        )

        res = empty_result(data="Scheduled job to renew certificates")
        res["job_id"] = job_id

        headers: dict[str, str] = {}
        if total_count:
            headers["X-Total-Count"] = str(total_count)
        return CnaasJSONResponse(content=res, headers=headers)
    else:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data=f"Unknown action specified: {action}"),
        )


# ---------------------------------------------------------------------------
# 20. DeviceStackmembersApi  GET /device/{hostname}/stackmembers
# ---------------------------------------------------------------------------


@router.get("/device/{hostname}/stackmembers")
def get_stackmembers(hostname: str, user: str = Depends(get_current_user)):
    """Get stackmembers for device."""
    result = empty_result(data={"stackmembers": []})
    with sqla_session() as session:
        device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not device:
            return CnaasJSONResponse(status_code=404, content=empty_result("error", "Device not found"))
        stackmembers = device.get_stackmembers(session)
        for stackmember in stackmembers:
            result["data"]["stackmembers"].append(stackmember.as_dict())
    return result


# ---------------------------------------------------------------------------
# 20. DeviceStackmembersApi  PUT /device/{hostname}/stackmembers
# ---------------------------------------------------------------------------


@router.put("/device/{hostname}/stackmembers")
def update_stackmembers(
    hostname: str,
    json_data: dict[str, Any],
    user: str = Depends(get_current_user),
):
    """Update stackmembers for device."""
    try:
        validated_json_data = StackmembersModel(**json_data).model_dump()
        data = validated_json_data["stackmembers"]
    except ValidationError as e:
        errors = format_stackmember_errors(e.errors())
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result("error", errors),
        )
    result = empty_result(data={"stackmembers": []})
    with sqla_session() as session:
        device_instance = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not device_instance:
            return CnaasJSONResponse(status_code=404, content=empty_result("error", "Device not found"))
        try:
            for stackmember in device_instance.get_stackmembers(session):
                session.delete(stackmember)
            session.flush()
            for stackmember_data in data:
                stackmember_data["device_id"] = device_instance.id
                new_stackmember = Stackmember(**stackmember_data)
                session.add(new_stackmember)
                result["data"]["stackmembers"].append(new_stackmember.as_dict())
        except ValueError as e:
            session.rollback()
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result("error", str(e)),
            )
    return result


# ---------------------------------------------------------------------------
# 21. DeviceSyncHistoryApi  GET /device/{hostname}/synchistory
# ---------------------------------------------------------------------------


@router.get("/device/{hostname}/synchistory")
def get_synchistory(hostname: str, user: str = Depends(get_current_user)):
    """Get sync history for device."""
    result = empty_result()
    result["data"] = {"hostnames": {}}
    sync_history: SyncHistory

    if not Device.valid_hostname(hostname):
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="Invalid hostname specified"),
        )
    sync_history = get_sync_events([hostname])

    result["data"]["hostnames"] = sync_history.asdict()
    return result


# ---------------------------------------------------------------------------
# 21. DeviceSyncHistoryApi  POST /device/{hostname}/synchistory
# ---------------------------------------------------------------------------


@router.post("/device/{hostname}/synchistory")
def add_synchistory_event(
    hostname: str,
    json_data: dict[str, Any],
    user: str = Depends(get_current_user),
):
    """Add a sync history event."""
    try:
        validated_json_data = NewSyncEventModel(**json_data).model_dump()
    except ValidationError as e:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result("error", parse_pydantic_error(e, NewSyncEventModel, json_data)),
        )
    with sqla_session() as session:
        device_instance = session.query(Device).filter(Device.hostname == validated_json_data["hostname"]).one_or_none()
        if not device_instance:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result("error", "Device not found"),
            )
    try:
        add_sync_event(**validated_json_data)
    except Exception as e:
        return CnaasJSONResponse(
            status_code=500,
            content=empty_result("error", str(e)),
        )
    return empty_result(data=validated_json_data)


# ---------------------------------------------------------------------------
# 21. DeviceSyncHistoryApi  DELETE /device/{hostname}/synchistory
# ---------------------------------------------------------------------------


@router.delete("/device/{hostname}/synchistory")
def delete_synchistory(hostname: str, user: str = Depends(get_current_user)):
    """Delete sync history for device."""
    if not Device.valid_hostname(hostname):
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result(status="error", data="Invalid hostname specified"),
        )
    with sqla_session() as session:
        device_instance = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not device_instance:
            return CnaasJSONResponse(
                status_code=404,
                content=empty_result("error", "Device not found"),
            )
    try:
        remove_sync_events(hostname)
    except Exception as e:
        return CnaasJSONResponse(
            status_code=500,
            content=empty_result("error", str(e)),
        )
    return empty_result(status="success", data=f"Removed sync events for {hostname}")
