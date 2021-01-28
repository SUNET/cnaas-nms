from flask import request
from flask_restx import Resource, Namespace, fields
from flask_jwt_extended import jwt_required
from ipaddress import IPv4Network

from cnaas_nms.api.generic import empty_result
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.confpush.underlay import find_free_infra_linknet
from cnaas_nms.version import __api_version__


api = Namespace('linknets', description='API for handling links',
                prefix='/api/{}'.format(__api_version__))

linknet_model = api.model('linknet', {
    'device_a': fields.String(required=True),
    'device_b': fields.String(required=True),
    'device_a_port': fields.String(required=True),
    'device_b_port': fields.String(required=True),
})


class LinknetsApi(Resource):
    @jwt_required
    def get(self):
        """ Get all linksnets """
        result = {'linknets': []}
        with sqla_session() as session:
            query = session.query(Linknet)
            for instance in query:
                result['linknets'].append(instance.as_dict())
        return empty_result(status='success', data=result)

    @jwt_required
    @api.expect(linknet_model)
    def post(self):
        """ Add a new linknet """
        json_data = request.get_json()
        data = {}
        errors = []
        if 'device_a' in json_data:
            if not Device.valid_hostname(json_data['device_a']):
                errors.append("Invalid hostname specified for device_a")
            else:
                hostname_a = json_data['device_a']
        else:
            errors.append("Required field hostname_a not found")
        if 'device_b' in json_data:
            if not Device.valid_hostname(json_data['device_b']):
                errors.append("Invalid hostname specified for device_b")
            else:
                hostname_b = json_data['device_b']
        else:
            errors.append("Required field hostname_b not found")
        if 'device_a_port' not in json_data:
            errors.append("Required field device_a_port not found")
        if 'device_b_port' not in json_data:
            errors.append("Required field device_b_port not found")

        new_prefix = None
        if 'prefix' in json_data:
            if json_data['prefix']:
                try:
                    new_prefix = IPv4Network(json_data['prefix'])
                except Exception as e:
                    errors.append("Invalid prefix: {}".format(e))

        if errors:
            return empty_result(status='error', data=errors), 400

        with sqla_session() as session:
            dev_a: Device = session.query(Device).\
                filter(Device.hostname == hostname_a).one_or_none()
            if not dev_a:
                return empty_result(
                    status='error',
                    data=f"Hostname '{hostname_a}' not found or is in invalid state"
                ), 400

            dev_b: Device = session.query(Device). \
                filter(Device.hostname == hostname_b).one_or_none()
            if not dev_b:
                return empty_result(
                    status='error',
                    data=f"Hostname '{hostname_b}' not found or is in invalid state"
                ), 400

            # check if we need an ip prefix for the linknet
            ip_linknet_devtypes = [DeviceType.CORE, DeviceType.DIST]
            if dev_a.device_type in ip_linknet_devtypes and \
                    dev_b.device_type in ip_linknet_devtypes:
                if not new_prefix:
                    new_prefix = find_free_infra_linknet(session)
                if not new_prefix:
                    return empty_result(
                        status='error',
                        data="Device types requires IP linknets, but no prefix could be found"
                    ), 400

            try:
                new_linknet = Linknet.create_linknet(
                    session, hostname_a, json_data['device_a_port'],
                    hostname_b, json_data['device_b_port'], new_prefix)
                session.add(new_linknet)
                session.commit()
                data = new_linknet.as_dict()
            except Exception as e:
                session.rollback()
                return empty_result(status='error', data=str(e)), 500

        return empty_result(status='success', data=data), 201

    @jwt_required
    def delete(self):
        """ Remove linknet """
        json_data = request.get_json()
        errors = []
        if 'id' not in json_data:
            errors.append("Required field id not found")
        elif not isinstance(json_data['id'], int):
            errors.append("Field id must be an integer")
        if errors:
            return empty_result(status='error', data=errors), 400

        with sqla_session() as session:
            cur_linknet = session.query(Linknet).filter(Linknet.id == json_data['id']).one_or_none()
            if not cur_linknet:
                return empty_result(status='error', data="No such linknet found in database"), 404
            session.delete(cur_linknet)
            session.commit()
            return empty_result(status="success", data={"deleted_linknet": cur_linknet.as_dict()}), 200


# # Links
api.add_resource(LinknetsApi, '')
