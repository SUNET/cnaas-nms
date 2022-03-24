from ipaddress import IPv4Address, IPv4Network
from typing import Optional

from flask import request
from flask_restx import Namespace, Resource, fields
from pydantic import BaseModel, validator
from pydantic.error_wrappers import ValidationError

from cnaas_nms.api.generic import empty_result, parse_pydantic_error, update_sqla_object
from cnaas_nms.confpush.underlay import find_free_infra_linknet
from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.session import sqla_session
from cnaas_nms.tools.security import jwt_required
from cnaas_nms.version import __api_version__

linknets_api = Namespace("linknets", description="API for handling linknets", prefix="/api/{}".format(__api_version__))
linknet_api = Namespace(
    "linknet", description="API for handling a single linknet", prefix="/api/{}".format(__api_version__)
)

linknets_model = linknets_api.model(
    "linknets",
    {
        "device_a": fields.String(required=True),
        "device_b": fields.String(required=True),
        "device_a_port": fields.String(required=True),
        "device_b_port": fields.String(required=True),
        "ipv4_network": fields.String(required=False),
    },
)


linknet_model = linknet_api.model(
    "linknet",
    {
        "device_a": fields.String(required=False),
        "device_b": fields.String(required=False),
        "device_a_port": fields.String(required=False),
        "device_b_port": fields.String(required=False),
        "ipv4_network": fields.String(required=False),
        "device_a_ip": fields.String(required=False),
        "device_b_ip": fields.String(required=False),
    },
)


class f_linknet(BaseModel):
    ipv4_network: Optional[str] = None
    device_a_ip: Optional[str] = None
    device_b_ip: Optional[str] = None

    @validator("device_a_ip", "device_b_ip")
    def device_ip_validator(cls, v, values, **kwargs):
        if not v:
            return v
        if not values["ipv4_network"]:
            raise ValueError("ipv4_network must be set")
        try:
            addr = IPv4Address(v)
            net = IPv4Network(values["ipv4_network"])
        except ValueError:
            raise ValueError("Invalid device IP or ipv4_network")
        else:
            if addr not in net.hosts():
                raise ValueError("device IP must be part of ipv4_network")
            if "device_a_ip" in values and v == values["device_a_ip"]:
                raise ValueError("device_a_ip and device_b_ip can not be the same")
            if "device_b_ip" in values and v == values["device_b_ip"]:
                raise ValueError("device_a_ip and device_b_ip can not be the same")

        return v

    @validator("ipv4_network")
    def ipv4_network_validator(cls, v, values, **kwargs):
        if not v:
            return v
        try:
            net = IPv4Network(v)
            prefix_len = int(net.prefixlen)
        except ValueError:
            raise ValueError("Invalid ipv4_network received. Must be IPv4 network address with mask")
        else:
            if prefix_len < 29:
                raise ValueError("Bad prefix length {} for linknet network".format(prefix_len))

        return v


class LinknetsApi(Resource):
    @staticmethod
    def validate_hostname(hostname):
        if not Device.valid_hostname(hostname):
            raise ValueError("Invalid hostname: {}".format(hostname))
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
            if not dev:
                raise ValueError("Hostname {} not found in database")
            # Allow pre-provisioning of linknet to device that is not yet
            # managed or not assigned device_type, so no further checks here

    @jwt_required
    def get(self):
        """Get all linksnets."""
        result = {"linknets": []}
        with sqla_session() as session:
            query = session.query(Linknet)
            for instance in query:
                result["linknets"].append(instance.as_dict())
        return empty_result(status="success", data=result)

    @jwt_required
    @linknets_api.expect(linknets_model)
    def post(self):
        """Add a new linknet."""
        json_data = request.get_json()
        errors = []
        for device_arg in ["device_a", "device_b"]:
            if device_arg in json_data:
                try:
                    self.validate_hostname(json_data[device_arg])
                except ValueError as e:
                    errors.append("Bad parameter {}: {}".format(device_arg, e))
            else:
                errors.append("Required field {} not found".format(device_arg))

        if "device_a_port" not in json_data:
            errors.append("Required field device_a_port not found")
        if "device_b_port" not in json_data:
            errors.append("Required field device_b_port not found")

        new_prefix = None
        if "ipv4_network" in json_data:
            if json_data["ipv4_network"]:
                try:
                    new_prefix = IPv4Network(json_data["ipv4_network"])
                except Exception as e:
                    errors.append("Invalid ipv4_network: {}".format(e))

        if errors:
            return empty_result(status="error", data=errors), 400

        with sqla_session() as session:
            dev_a: Device = session.query(Device).filter(Device.hostname == json_data["device_a"]).one_or_none()
            if not dev_a:
                return empty_result(status="error", data="Hostname '{}' not found".format(json_data["device_a"])), 500

            dev_b: Device = session.query(Device).filter(Device.hostname == json_data["device_b"]).one_or_none()
            if not dev_b:
                return empty_result(status="error", data="Hostname '{}' not found".format(json_data["device_b"])), 500

            # check if we need an ip prefix for the linknet
            ip_linknet_devtypes = [DeviceType.CORE, DeviceType.DIST]
            if dev_a.device_type in ip_linknet_devtypes and dev_b.device_type in ip_linknet_devtypes:
                if not new_prefix:
                    new_prefix = find_free_infra_linknet(session)
                if not new_prefix:
                    return (
                        empty_result(
                            status="error", data="Device types requires IP linknets, but no prefix could be found"
                        ),
                        400,
                    )

            try:
                new_linknet = Linknet.create_linknet(
                    session,
                    json_data["device_a"],
                    json_data["device_a_port"],
                    json_data["device_b"],
                    json_data["device_b_port"],
                    new_prefix,
                )
                session.add(new_linknet)
                session.commit()
                data = new_linknet.as_dict()
            except Exception as e:
                session.rollback()
                return empty_result(status="error", data=str(e)), 500

        return empty_result(status="success", data=data), 201

    @jwt_required
    def delete(self):
        """Remove linknet."""
        json_data = request.get_json()
        errors = []
        if "id" not in json_data:
            errors.append("Required field id not found")
        elif not isinstance(json_data["id"], int):
            errors.append("Field id must be an integer")
        if errors:
            return empty_result(status="error", data=errors), 400

        with sqla_session() as session:
            cur_linknet: Linknet = session.query(Linknet).filter(Linknet.id == json_data["id"]).one_or_none()
            if not cur_linknet:
                return empty_result(status="error", data="No such linknet found in database"), 404
            cur_linknet.device_a.synchronized = False
            cur_linknet.device_b.synchronized = False
            session.delete(cur_linknet)
            session.commit()
            return empty_result(status="success", data={"deleted_linknet": cur_linknet.as_dict()}), 200


class LinknetByIdApi(Resource):
    @jwt_required
    def get(self, linknet_id):
        """Get a single specified linknet."""
        result = empty_result()
        result["data"] = {"linknets": []}
        with sqla_session() as session:
            instance = session.query(Linknet).filter(Linknet.id == linknet_id).one_or_none()
            if instance:
                result["data"]["linknets"].append(instance.as_dict())
            else:
                return empty_result("error", "Linknet not found"), 404
        return result

    @jwt_required
    def delete(self, linknet_id):
        """Remove a linknet."""
        with sqla_session() as session:
            instance: Linknet = session.query(Linknet).filter(Linknet.id == linknet_id).one_or_none()
            if instance:
                instance.device_a.synchronized = False
                instance.device_b.synchronized = False
                session.delete(instance)
                session.commit()
                return empty_result(status="success", data={"deleted_linknet": instance.as_dict()}), 200
            else:
                return empty_result("error", "No such linknet found in database"), 404

    @jwt_required
    @linknets_api.expect(linknet_model)
    def put(self, linknet_id):
        """Update data on existing linknet."""
        json_data = request.get_json()
        errors = []
        for device_arg in ["device_a", "device_b"]:
            if device_arg in json_data:
                try:
                    LinknetsApi.validate_hostname(json_data[device_arg])
                except ValueError as e:
                    errors.append("Bad parameter {}: {}".format(device_arg, e))

        if errors:
            return empty_result(status="error", data=errors), 400

        with sqla_session() as session:
            instance: Linknet = session.query(Linknet).filter(Linknet.id == linknet_id).one_or_none()
            if instance:
                try:
                    validate_data = {**instance.as_dict(), **json_data}
                    f_linknet(**validate_data).dict()
                except ValidationError as e:
                    errors += parse_pydantic_error(e, f_linknet, validate_data)
                if errors:
                    return empty_result(status="error", data=errors), 400

                changed: bool = update_sqla_object(instance, json_data)
                if changed:
                    instance.device_a.synchronized = False
                    instance.device_b.synchronized = False
                    return empty_result(status="success", data={"updated_linknet": instance.as_dict()}), 200
                else:
                    return empty_result(status="success", data={"unchanged_linknet": instance.as_dict()}), 200
            else:
                return empty_result(status="error", data="linknet not found"), 400


# Links
linknets_api.add_resource(LinknetsApi, "")
linknet_api.add_resource(LinknetByIdApi, "/<int:linknet_id>")
