from ipaddress import IPv4Interface, IPv6Interface
from typing import Optional

from flask import request
from flask_restx import Namespace, Resource, fields
from pydantic import BaseModel, ValidationError, validator
from sqlalchemy.exc import IntegrityError

from cnaas_nms.api.generic import build_filter, empty_result, limit_results, parse_pydantic_error, update_sqla_object
from cnaas_nms.db.device import Device
from cnaas_nms.db.mgmtdomain import Mgmtdomain
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.settings_fields import vlan_id_schema_optional
from cnaas_nms.devicehandler.sync_history import add_sync_event
from cnaas_nms.tools.security import get_identity, login_required
from cnaas_nms.version import __api_version__

mgmtdomains_api = Namespace(
    "mgmtdomains", description="API for handling management domains", prefix="/api/{}".format(__api_version__)
)
mgmtdomain_api = Namespace(
    "mgmtdomain", description="API for handling a single management domain", prefix="/api/{}".format(__api_version__)
)

mgmtdomain_model = mgmtdomain_api.model(
    "mgmtdomain",
    {
        "device_a": fields.String(required=True),
        "device_b": fields.String(required=True),
        "vlan": fields.Integer(required=True),
        "ipv4_gw": fields.String(required=True),
        "ipv6_gw": fields.String(required=True),
        "description": fields.String(required=False),
    },
)


class f_mgmtdomain(BaseModel):
    vlan: Optional[int] = vlan_id_schema_optional
    ipv4_gw: Optional[str] = None
    ipv6_gw: Optional[str] = None
    description: Optional[str] = None

    @validator("ipv4_gw")
    def ipv4_gw_valid_address(cls, v, values, **kwargs):
        try:
            addr = IPv4Interface(v)
            prefix_len = int(addr.network.prefixlen)
        except Exception:  # noqa: S110
            raise ValueError("Invalid ipv4_gw received. Must be correct IPv4 address with mask")
        else:
            if addr.ip == addr.network.network_address:
                raise ValueError("Specify gateway address, not subnet address")
            if addr.ip == addr.network.broadcast_address:
                raise ValueError("Specify gateway address, not broadcast address")
            if prefix_len >= 31 or prefix_len <= 16:
                raise ValueError("Bad prefix length {} for management network".format(prefix_len))

        return v

    @validator("ipv6_gw")
    @classmethod
    def ipv6_gw_valid_address(cls, v, values, **kwargs):
        try:
            addr = IPv6Interface(v)
            prefix_len = int(addr.network.prefixlen)
        except Exception:  # noqa: S110
            raise ValueError("Invalid ipv6_gw received. Must be correct IPv6 address with mask")
        else:
            if addr.ip == addr.network.network_address:
                raise ValueError("Specify gateway address, not subnet address")
            if addr.ip == addr.network.broadcast_address:
                raise ValueError("Specify gateway address, not broadcast address")
            if prefix_len >= 126 or prefix_len <= 63:
                raise ValueError("Bad prefix length {} for management network".format(prefix_len))

        return v


class MgmtdomainByIdApi(Resource):
    @login_required
    def get(self, mgmtdomain_id):
        """Get management domain by ID"""
        result = empty_result()
        result["data"] = {"mgmtdomains": []}
        with sqla_session() as session:
            instance = session.query(Mgmtdomain).filter(Mgmtdomain.id == mgmtdomain_id).one_or_none()
            if instance:
                result["data"]["mgmtdomains"].append(instance.as_dict())
            else:
                return empty_result("error", "Management domain not found"), 404
        return result

    @login_required
    def delete(self, mgmtdomain_id):
        """Remove management domain"""
        with sqla_session() as session:
            instance: Mgmtdomain = session.query(Mgmtdomain).filter(Mgmtdomain.id == mgmtdomain_id).one_or_none()
            if instance:
                instance.device_a.synchronized = False
                add_sync_event(instance.device_a.hostname, "mgmtdomain_deleted", get_identity())
                instance.device_b.synchronized = False
                add_sync_event(instance.device_b.hostname, "mgmtdomain_deleted", get_identity())
                session.delete(instance)
                session.commit()
                return empty_result(status="success", data={"deleted_mgmtdomain": instance.as_dict()}), 200
            else:
                return empty_result("error", "Management domain not found"), 404

    @login_required
    @mgmtdomain_api.expect(mgmtdomain_model)
    def put(self, mgmtdomain_id):
        """Modify management domain"""
        json_data = request.get_json()
        errors = []
        try:
            f_mgmtdomain(**json_data).dict()
        except ValidationError as e:
            errors += parse_pydantic_error(e, f_mgmtdomain, json_data)

        if errors:
            return empty_result("error", errors), 400

        with sqla_session() as session:
            instance: Mgmtdomain = session.query(Mgmtdomain).filter(Mgmtdomain.id == mgmtdomain_id).one_or_none()
            if instance:
                changed: bool = update_sqla_object(instance, json_data)
                if changed:
                    instance.device_a.synchronized = False
                    add_sync_event(instance.device_a.hostname, "mgmtdomain_updated", get_identity())
                    instance.device_b.synchronized = False
                    add_sync_event(instance.device_b.hostname, "mgmtdomain_updated", get_identity())
                    return empty_result(status="success", data={"updated_mgmtdomain": instance.as_dict()}), 200
                else:
                    return empty_result(status="success", data={"unchanged_mgmtdomain": instance.as_dict()}), 200
            else:
                return empty_result(status="error", data="mgmtdomain not found"), 400


class MgmtdomainsApi(Resource):
    @login_required
    def get(self):
        """Get all management domains"""
        result = empty_result()
        result["data"] = {"mgmtdomains": []}
        with sqla_session() as session:
            query = session.query(Mgmtdomain)
            try:
                query = build_filter(Mgmtdomain, query).limit(limit_results())
            except Exception as e:
                return empty_result(status="error", data="Unable to filter mgmtdomains: {}".format(e)), 400
            for instance in query:
                result["data"]["mgmtdomains"].append(instance.as_dict())
        return result

    @login_required
    @mgmtdomain_api.expect(mgmtdomain_model)
    def post(self):
        """Add management domain"""
        json_data = request.get_json()
        data = {}
        errors = []
        with sqla_session() as session:
            if "device_a" in json_data:
                hostname_a = str(json_data["device_a"])
                if not Device.valid_hostname(hostname_a):
                    errors.append(f"Invalid hostname for device_a: {hostname_a}")
                else:
                    device_a: Device = session.query(Device).filter(Device.hostname == hostname_a).one_or_none()
                    if not device_a:
                        errors.append(f"Device with hostname {hostname_a} not found")
                    else:
                        data["device_a"] = device_a
            if "device_b" in json_data:
                hostname_b = str(json_data["device_b"])
                if not Device.valid_hostname(hostname_b):
                    errors.append(f"Invalid hostname for device_b: {hostname_b}")
                else:
                    device_b: Device = session.query(Device).filter(Device.hostname == hostname_b).one_or_none()
                    if not device_b:
                        errors.append(f"Device with hostname {hostname_b} not found")
                    else:
                        data["device_b"] = device_b

            try:
                data = {**data, **f_mgmtdomain(**json_data).dict()}
            except ValidationError as e:
                errors += parse_pydantic_error(e, f_mgmtdomain, json_data)

            required_keys_1 = ["device_a", "device_b", "vlan", "ipv4_gw"]
            required_keys_2 = ["device_a", "device_b", "vlan", "ipv6_gw"]
            required_in_data = all(key in data for key in required_keys_1) or all(
                key in data for key in required_keys_2
            )
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
                    if "duplicate" in str(e):
                        return empty_result("error", "Duplicate value: {}".format(e.orig.args[0])), 400
                    else:
                        return empty_result("error", "Integrity error: {}".format(e)), 400

                device_a.synchronized = False
                add_sync_event(device_a.hostname, "mgmtdomain_created", get_identity())
                device_b.synchronized = False
                add_sync_event(device_b.hostname, "mgmtdomain_created", get_identity())
                return empty_result(status="success", data={"added_mgmtdomain": new_mgmtd.as_dict()}), 200
            else:
                errors.append(
                    "Not all required inputs were found: {} OR {}".format(
                        ", ".join(required_keys_1), ", ".join(required_keys_2)
                    )
                )
                return empty_result("error", errors), 400


mgmtdomains_api.add_resource(MgmtdomainsApi, "")
mgmtdomain_api.add_resource(MgmtdomainByIdApi, "/<int:mgmtdomain_id>")
