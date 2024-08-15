from typing import List

from flask import request
from flask_restx import Namespace, Resource, fields

from cnaas_nms.api.generic import empty_result
from cnaas_nms.db.device import Device
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.settings import get_settings
from cnaas_nms.devicehandler.interface_state import bounce_interfaces, get_interface_states
from cnaas_nms.devicehandler.sync_devices import resolve_vlanid, resolve_vlanid_list
from cnaas_nms.devicehandler.sync_history import add_sync_event
from cnaas_nms.tools.security import get_identity, login_required
from cnaas_nms.version import __api_version__

api = Namespace("device", description="API for handling interfaces", prefix="/api/{}".format(__api_version__))

interfacedata_model = api.model(
    "interfacedata",
    {
        "untagged_vlan": fields.Raw(required=False, description="VLAN ID or name", example="STUDENTS"),
        "tagged_vlan_list": fields.List(
            fields.Raw(), required=False, description="List of VLAN IDs or names", example=["STUDENTS", "EMPLOYEES"]
        ),
        "description": fields.String(required=False, description="Interface description", example="Access point"),
        "enabled": fields.Boolean(required=False, example=True),
        "aggregate_id": fields.Integer(required=False, example=-1, description="LACP ID"),
        "bpdu_filter": fields.Boolean(required=False, example=True),
        "redundant_link": fields.Boolean(required=False, example=True),
        "tags": fields.List(fields.String(), required=False, description="List of tags", example=["tag1", "tag2"]),
        "cli_append_str": fields.String(required=False),
    },
)

interface_model = api.model(
    "interface",
    {
        "configtype": fields.String(
            required=True,
            description=(
                "Type of interface, can be: ACCESS_AUTO, ACCESS_UNTAGGED, ACCESS_TAGGED, "
                "ACCESS_UPLINK, ACCESS_DOWNLINK, MLAG_PEER"
            ),
            example="ACCESS_AUTO",
        ),
        "data": fields.Nested(interfacedata_model),
    },
)

interfacename_model = api.model(
    "interfacename",
    {
        "interfacename": fields.Nested(interface_model, required=True),
    },
)

interfaces_model = api.model(
    "interfaces",
    {
        "interfaces": fields.Nested(interfacename_model, required=True),
    },
)


class InterfaceApi(Resource):
    @login_required
    def get(self, hostname):
        """List all interfaces"""
        result = empty_result()
        result["data"] = {"interfaces": []}
        with sqla_session() as session:
            dev = session.query(Device).filter(Device.hostname == hostname).one_or_none()
            if not dev:
                return empty_result("error", "Device not found"), 404
            result["data"]["hostname"] = dev.hostname
            intfs = session.query(Interface).filter(Interface.device == dev).all()
            intf: Interface
            interfaces = []
            for intf in intfs:
                ifdict = intf.as_dict()
                ifdict["indexnum"] = Interface.interface_index_num(ifdict["name"])
                interfaces.append(ifdict)
            result["data"]["interfaces"] = sorted(interfaces, key=lambda i: i["indexnum"])
        return result

    @login_required
    @api.expect(interfaces_model)
    def put(self, hostname):
        """Take a map of interfaces and associated values to update.
        Example:
            {"interfaces": {"Ethernet1": {"configtype": "ACCESS_AUTO"}}}
        """
        json_data = request.get_json()
        data = {}
        errors = []
        device_settings = None

        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
            if not dev:
                return empty_result("error", "Device not found"), 404

            updated = False
            if "interfaces" in json_data and isinstance(json_data["interfaces"], dict):
                for if_name, if_dict in json_data["interfaces"].items():
                    if not isinstance(if_dict, dict):
                        errors.append("Each interface must have a dict with data to update")
                        continue
                    intf: Interface = (
                        session.query(Interface)
                        .filter(Interface.device == dev)
                        .filter(Interface.name == if_name)
                        .one_or_none()
                    )
                    if not intf:
                        errors.append(f"Interface {if_name} not found")
                        continue
                    if intf.data and isinstance(intf.data, dict):
                        intfdata_original = dict(intf.data)
                        intfdata = dict(intf.data)
                    else:
                        intfdata_original = {}
                        intfdata = {}

                    if "configtype" in if_dict and if_dict["configtype"]:
                        try:
                            configtype = if_dict["configtype"].upper()
                        except AttributeError:
                            errors.append("configtype is not a string")
                        else:
                            if InterfaceConfigType.has_name(configtype):
                                if intf.configtype != InterfaceConfigType[configtype]:
                                    intf.configtype = InterfaceConfigType[configtype]
                                    updated = True
                                    data[if_name] = {"configtype": configtype}
                            else:
                                errors.append(f"Invalid configtype received: {configtype}")

                    if "data" in if_dict and if_dict["data"]:
                        # TODO: maybe this validation should be done via
                        #  pydantic if it gets more complex
                        if not device_settings:
                            device_settings, _ = get_settings(hostname, dev.device_type)
                        if "vxlan" in if_dict["data"]:
                            if if_dict["data"]["vxlan"] in device_settings["vxlans"]:
                                intfdata["vxlan"] = if_dict["data"]["vxlan"]
                            else:
                                errors.append(
                                    "Specified VXLAN {} is not present in {}".format(if_dict["data"]["vxlan"], hostname)
                                )
                        if "untagged_vlan" in if_dict["data"]:
                            if if_dict["data"]["untagged_vlan"] is None:
                                if "untagged_vlan" in intfdata:
                                    del intfdata["untagged_vlan"]
                            else:
                                vlan_id = resolve_vlanid(if_dict["data"]["untagged_vlan"], device_settings["vxlans"])
                                if vlan_id:
                                    intfdata["untagged_vlan"] = if_dict["data"]["untagged_vlan"]
                                else:
                                    errors.append(
                                        "Specified VLAN name {} is not present in {}".format(
                                            if_dict["data"]["untagged_vlan"], hostname
                                        )
                                    )
                        if "tagged_vlan_list" in if_dict["data"]:
                            if isinstance(if_dict["data"]["tagged_vlan_list"], list):
                                vlan_id_list = resolve_vlanid_list(
                                    if_dict["data"]["tagged_vlan_list"], device_settings["vxlans"]
                                )
                                if len(vlan_id_list) == len(if_dict["data"]["tagged_vlan_list"]):
                                    intfdata["tagged_vlan_list"] = if_dict["data"]["tagged_vlan_list"]
                                else:
                                    errors.append(
                                        "Some VLAN names {} are not present in {}".format(
                                            ", ".join(if_dict["data"]["tagged_vlan_list"]), hostname
                                        )
                                    )
                            else:
                                errors.append(
                                    "tagged_vlan_list should be of type list, found {}".format(
                                        type(if_dict["data"]["tagged_vlan_list"])
                                    )
                                )
                        if "neighbor" in if_dict["data"]:
                            if isinstance(if_dict["data"]["neighbor"], str) and Device.valid_hostname(
                                if_dict["data"]["neighbor"]
                            ):
                                intfdata["neighbor"] = if_dict["data"]["neighbor"]
                            elif if_dict["data"]["neighbor"] is None:
                                if "neighbor" in intfdata:
                                    del intfdata["neighbor"]
                            else:
                                errors.append(
                                    "Neighbor must be valid hostname, got: {}".format(if_dict["data"]["neighbor"])
                                )
                        if "neighbor_id" in if_dict["data"]:
                            if isinstance(if_dict["data"]["neighbor_id"], int):
                                intfdata["neighbor_id"] = if_dict["data"]["neighbor_id"]
                            elif if_dict["data"]["neighbor_id"] is None:
                                if "neighbor_id" in intfdata:
                                    del intfdata["neighbor_id"]
                            else:
                                errors.append(
                                    "Neighbor_id must be valid integer, got: {}".format(if_dict["data"]["neighbor_id"])
                                )
                        if "description" in if_dict["data"]:
                            if (
                                isinstance(if_dict["data"]["description"], str)
                                and len(if_dict["data"]["description"]) <= 64
                            ):
                                if if_dict["data"]["description"]:
                                    intfdata["description"] = if_dict["data"]["description"]
                                elif "description" in intfdata:
                                    del intfdata["description"]
                            elif if_dict["data"]["description"] is None:
                                if "description" in intfdata:
                                    del intfdata["description"]
                            else:
                                errors.append(
                                    "Description must be a string of 0-64 characters, got: {}".format(
                                        if_dict["data"]["description"]
                                    )
                                )
                        if "enabled" in if_dict["data"]:
                            if type(if_dict["data"]["enabled"]) is bool:
                                intfdata["enabled"] = if_dict["data"]["enabled"]
                            else:
                                errors.append(
                                    "Enabled must be a bool, true or false, got: {}".format(if_dict["data"]["enabled"])
                                )
                        if "aggregate_id" in if_dict["data"]:
                            if type(if_dict["data"]["aggregate_id"]) is int:
                                intfdata["aggregate_id"] = if_dict["data"]["aggregate_id"]
                            elif if_dict["data"]["aggregate_id"] is None:
                                if "aggregate_id" in intfdata:
                                    del intfdata["aggregate_id"]
                            else:
                                errors.append(
                                    "Aggregate ID must be an integer: {}".format(if_dict["data"]["aggregate_id"])
                                )
                        if "bpdu_filter" in if_dict["data"]:
                            if type(if_dict["data"]["bpdu_filter"]) is bool:
                                intfdata["bpdu_filter"] = if_dict["data"]["bpdu_filter"]
                            else:
                                errors.append(
                                    "bpdu_filter must be a bool, true or false, got: {}".format(
                                        if_dict["data"]["bpdu_filter"]
                                    )
                                )
                        if "redundant_link" in if_dict["data"]:
                            if type(if_dict["data"]["redundant_link"]) is bool:
                                intfdata["redundant_link"] = if_dict["data"]["redundant_link"]
                            else:
                                errors.append(
                                    "redundant_link must be a bool, true or false, got: {}".format(
                                        if_dict["data"]["redundant_link"]
                                    )
                                )
                        if "tags" in if_dict["data"]:
                            if isinstance(if_dict["data"]["tags"], list):
                                intfdata["tags"] = if_dict["data"]["tags"]
                            else:
                                errors.append(
                                    "tags should be of type list, found {}".format(type(if_dict["data"]["tags"]))
                                )
                        if "cli_append_str" in if_dict["data"]:
                            if isinstance(if_dict["data"]["cli_append_str"], str):
                                intfdata["cli_append_str"] = if_dict["data"]["cli_append_str"]
                            else:
                                errors.append(
                                    "cli_append_str must be a string, got: {}".format(if_dict["data"]["cli_append_str"])
                                )
                    elif "data" in if_dict and not if_dict["data"]:
                        intfdata = None

                    if intfdata != intfdata_original:
                        intf.data = intfdata
                        updated = True
                        if if_name in data:
                            data[if_name]["data"] = intfdata
                        else:
                            data[if_name] = {"data": intfdata}

            if updated:
                dev.synchronized = False
                add_sync_event(hostname, "interface_updated", get_identity())

        if errors:
            if data:
                ret = {"errors": errors, "updated": data}
            else:
                ret = {"errors": errors}
            return empty_result(status="error", data=ret), 400
        else:
            return empty_result(status="success", data={"updated": data})


class InterfaceStatusApi(Resource):
    @login_required
    def get(self, hostname):
        """List all interfaces status"""
        result = empty_result()
        try:
            result["data"] = {"interface_status": get_interface_states(hostname)}
        except ValueError as e:
            return empty_result("error", "Could not get interface states, invalid input: {}".format(e)), 400
        except Exception as e:
            return empty_result("error", "Could not get interface states, unknon exception: {}".format(e)), 400
        return result

    @login_required
    def put(self, hostname):
        """Bounce selected interfaces by appling bounce-down/bounce-up template"""
        json_data = request.get_json()

        if "bounce_interfaces" in json_data and isinstance(json_data["bounce_interfaces"], list):
            interfaces: List[str] = json_data["bounce_interfaces"]
            try:
                bounce_success = bounce_interfaces(hostname, interfaces)
            except ValueError as e:
                return empty_result(status="error", data=str(e)), 400
            except Exception as e:
                return empty_result(status="error", data=str(e)), 500

            if bounce_success:
                return empty_result(status="success", data="Bounced interfaces: {}".format(", ".join(interfaces)))
            else:
                return empty_result(
                    status="success", data="No error, but no interfaces changed state: {}".format(", ".join(interfaces))
                )
        else:
            return empty_result(status="error", data="Unknown action"), 400


api.add_resource(InterfaceApi, "/<string:hostname>/interfaces")
api.add_resource(InterfaceStatusApi, "/<string:hostname>/interface_status")
