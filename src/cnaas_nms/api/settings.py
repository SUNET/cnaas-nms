import json
from typing import Optional

from flask import make_response, request
from flask_restx import Namespace, Resource

from cnaas_nms.api.generic import empty_result
from cnaas_nms.app_settings import api_settings
from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.helper import json_dumper
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.settings import (
    FILE_MODEL_MAP,
    AccessListGenerationError,
    SettingsSyntaxError,
    _build_aerleon_definitions,
    check_settings_syntax,
    f_root,
    get_generated_access_lists,
    get_settings,
)
from cnaas_nms.tools.mergedict import merge_dict_origin
from cnaas_nms.tools.security import login_required
from cnaas_nms.version import __api_version__

api = Namespace("settings", description="Settings", prefix="/api/{}".format(__api_version__))


def validate_json_to_model(json_data):
    """Validate json_data by using check_settings_syntax"""
    syntax_dict, syntax_dict_origin = merge_dict_origin({}, json_data, {}, "API POST data")
    try:
        ret = check_settings_syntax(syntax_dict, syntax_dict_origin)
        if "access_lists" in syntax_dict:
            # Try to generate all access_lists and return any errors
            ret_copy = ret.copy()
            ret_copy["system_access_lists"] = list(ret_copy.get("access_lists", {}).keys())

            # Remove any keys without any value
            ret_copy = {k: v for k, v in ret_copy.items() if v}

            # Check if we can build aerleon definitions with the provided settings
            try:
                _build_aerleon_definitions(ret_copy)
            except AccessListGenerationError:
                # Default jmespath network reference if building definitions fails.
                # We just want to validate the access list generation and not the network definitions themselves.
                # TODO: Provide default values for the entire settings model so jmespath references can be properly validated.
                for net_name, net_defs in ret_copy["network_definitions"].items():
                    for net_def in net_defs:
                        if "path" in net_def.keys():
                            # Default to some random ips that should be valid for any network definition path.
                            ret_copy["network_definitions"][net_name] = [
                                {"address": "10.0.0.1"},  # noqa: S1313
                                {"address": "2001:db8::1"},  # noqa: S1313
                            ]
                            break

            get_generated_access_lists(platform="eos", settings=ret_copy)
    except SettingsSyntaxError as e:
        return empty_result(status="error", data=str(e)), 400
    except AccessListGenerationError as e:
        return empty_result(status="error", data=str(e)), 400
    else:
        return empty_result(status="success", data=ret)


class SettingsApi(Resource):
    @login_required
    @api.param("hostname")
    @api.param("device_type")
    def get(self):
        """Get settings"""
        args = request.args
        hostname = None
        device_type = None
        model = None
        if "hostname" in args:
            if Device.valid_hostname(args["hostname"]):
                hostname = args["hostname"]
            else:
                return empty_result("error", "Invalid hostname specified"), 400
            with sqla_session() as session:  # type: ignore
                dev: Optional[Device] = session.query(Device).filter(Device.hostname == hostname).one_or_none()
                if dev:
                    device_type = dev.device_type
                    model = dev.model
                    session.expunge(dev)
                else:
                    return empty_result("error", "Hostname not found in database"), 400
        if "device_type" in args:
            if DeviceType.has_name(args["device_type"].upper()):
                device_type = DeviceType[args["device_type"].upper()]
            else:
                return empty_result("error", "Invalid device type specified"), 400

        try:
            settings, settings_origin = get_settings(dev, device_type, model)
        except Exception as e:
            return empty_result("error", "Error getting settings: {}".format(str(e))), 400

        return empty_result(data={"settings": settings, "settings_origin": settings_origin})


class SettingsModelApi(Resource):
    def get(self):
        response = make_response(f_root.model_json_schema())
        response.headers["Content-Type"] = "application/json"
        return response

    def post(self):
        json_data = request.get_json()
        return validate_json_to_model(json_data)


class SettingsModelFilenameApi(Resource):
    def get(
        self,
        filename: str,
    ):
        f_model = FILE_MODEL_MAP.get(filename)
        if not f_model:
            return empty_result(status="error", data=f"Filename: '{filename}' does not map to any model."), 400
        response = make_response(f_model.model_json_schema())
        response.headers["Content-Type"] = "application/json"
        return response

    def post(self, filename: str):
        json_data = request.get_json()
        f_model = FILE_MODEL_MAP.get(filename)
        if not f_model:
            return empty_result(status="error", data=f"Filename: '{filename}' does not map to any model."), 400

        # Find out if there are any keys not meant to go in this file.
        filtered_keys = set(f_model.model_construct(**json_data).model_dump(exclude_unset=True).keys())
        json_data_keys = set(json_data.keys())
        not_valid_keys = json_data_keys - filtered_keys
        if not_valid_keys:
            return empty_result(
                status="error",
                data=f"Key{'s' if len(not_valid_keys) > 1 else ''}: '{', '.join(sorted(not_valid_keys))}' cannot be used in this file and will be filtered, please move them to the correct settings file.",
            ), 400
        return validate_json_to_model(json_data)


class SettingsServerApI(Resource):
    @login_required
    def get(self):
        ret_dict = {"api": api_settings.model_dump()}
        response = make_response(json.dumps(ret_dict, default=json_dumper))
        response.headers["Content-Type"] = "application/json"
        return response


api.add_resource(SettingsApi, "")
api.add_resource(SettingsModelApi, "/model")
api.add_resource(SettingsModelFilenameApi, "/model/<string:filename>")
api.add_resource(SettingsServerApI, "/server")
