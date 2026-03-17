import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from cnaas_nms.api.dependencies import get_current_user
from cnaas_nms.api.response import CnaasJSONResponse, empty_result
from cnaas_nms.app_settings import api_settings
from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.helper import json_dumper
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.settings import (
    AccessListGenerationError,
    SettingsSyntaxError,
    check_settings_syntax,
    check_system_access_lists,
    get_generated_access_lists,
    get_settings,
    get_settings_root,
)
from cnaas_nms.tools.mergedict import merge_dict_origin

router = APIRouter(tags=["settings"])

settings_root_model = get_settings_root()


@router.get("/settings")
def get_settings_api(
    hostname: Optional[str] = Query(None),
    device_type: Optional[str] = Query(None),
    user: str = Depends(get_current_user),
):
    """Get settings."""
    dev = None
    resolved_device_type = None
    model = None

    if hostname:
        if not Device.valid_hostname(hostname):
            return CnaasJSONResponse(status_code=400, content=empty_result("error", "Invalid hostname specified"))
        with sqla_session() as session:
            dev = session.query(Device).filter(Device.hostname == hostname).one_or_none()
            if dev:
                resolved_device_type = dev.device_type
                model = dev.model
                session.expunge(dev)
            else:
                return CnaasJSONResponse(status_code=400, content=empty_result("error", "Hostname not found in database"))

    if device_type:
        if DeviceType.has_name(device_type.upper()):
            resolved_device_type = DeviceType[device_type.upper()]
        else:
            return CnaasJSONResponse(status_code=400, content=empty_result("error", "Invalid device type specified"))

    try:
        settings, settings_origin = get_settings(dev, resolved_device_type, model)
    except Exception as e:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result("error", "Error getting settings: {}".format(str(e))),
        )

    return empty_result(data={"settings": settings, "settings_origin": settings_origin})


@router.get("/settings/model")
def get_settings_model():
    """Get the settings JSON schema."""
    return JSONResponse(content=settings_root_model.model_json_schema())


@router.post("/settings/model")
def validate_settings_model(request_body: dict[str, Any]):
    """Validate settings against the schema."""
    syntax_dict, syntax_dict_origin = merge_dict_origin({}, request_body, {}, "API POST data")
    try:
        ret = check_settings_syntax(syntax_dict, syntax_dict_origin)
        if "access_lists" in syntax_dict:
            ret_copy = ret.copy()
            ret_copy["system_access_lists"] = list(ret_copy.get("access_lists", {}).keys())
            get_generated_access_lists(platform="eos", settings=ret_copy)
        if "access_lists" in syntax_dict and "system_access_lists" in syntax_dict:
            check_system_access_lists(syntax_dict)
    except SettingsSyntaxError as e:
        return CnaasJSONResponse(status_code=400, content=empty_result(status="error", data=str(e)))
    except AccessListGenerationError as e:
        return CnaasJSONResponse(status_code=400, content=empty_result(status="error", data=str(e)))
    else:
        return empty_result(status="success", data=ret)


@router.get("/settings/server")
def get_settings_server(user: str = Depends(get_current_user)):
    """Get server settings."""
    ret_dict = {"api": api_settings.model_dump()}
    return JSONResponse(content=json.loads(json.dumps(ret_dict, default=json_dumper)))
