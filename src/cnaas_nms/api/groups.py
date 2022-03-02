from typing import List, Optional
import re

from flask_restx import Namespace, Resource

from cnaas_nms.db.device import Device, DeviceState
from cnaas_nms.api.generic import empty_result
from cnaas_nms.db.session import sqla_session

from cnaas_nms.db.settings import get_group_regex, get_groups
from cnaas_nms.tools.security import jwt_required
from cnaas_nms.version import __api_version__


api = Namespace('groups', description='API for handling groups',
                prefix='/api/{}'.format(__api_version__))


def groups_populate(group_name: Optional[str] = None):
    if group_name:
        tmpgroups: dict = {group_name: []}
    else:
        tmpgroups: dict = {key: [] for key in get_groups()}
    with sqla_session() as session:
        devices: List[Device] = session.query(Device).all()
        for dev in devices:
            groups = get_groups(dev.hostname)
            for group in groups:
                if group in tmpgroups:
                    tmpgroups[group].append(dev.hostname)
    return tmpgroups


def groups_osversion_populate(group_name: str):
    os_versions: dict = {}
    group_regex = get_group_regex(group_name)
    if group_regex:
        group_regex_p = re.compile(group_regex)
    else:
        raise ValueError("Could not find group {}".format(group_name))

    with sqla_session() as session:
        devices: List[Device] = session.query(Device).\
            filter(Device.state == DeviceState.MANAGED).\
            order_by(Device.hostname.asc()).all()
        for dev in devices:
            if not dev.os_version:
                continue
            if re.match(group_regex_p, dev.hostname):
                if dev.os_version in os_versions:
                    os_versions[dev.os_version].append(dev.hostname)
                else:
                    os_versions[dev.os_version] = [dev.hostname]
    return {group_name: os_versions}


class GroupsApi(Resource):
    @jwt_required()
    def get(self):
        """ Get all groups """
        tmpgroups = groups_populate()
        result = {'groups': tmpgroups}
        return empty_result(status='success', data=result)


class GroupsApiByName(Resource):
    @jwt_required()
    def get(self, group_name):
        """ Get a single group by name """
        tmpgroups = groups_populate(group_name)
        result = {'groups': tmpgroups}
        return empty_result(status='success', data=result)


class GroupsApiByNameOsversion(Resource):
    @jwt_required()
    def get(self, group_name):
        """Get os version of all devices in a group"""
        try:
            group_os_versions = groups_osversion_populate(group_name)
        except ValueError as e:
            return empty_result(
                status='error',
                data="Exception while getting group {}: {}".format(group_name, str(e))
            ), 404
        except Exception as e:
            return empty_result(
                status='error',
                data="Exception while getting group {}: {}".format(group_name, str(e))
            ), 500
        result = {'groups': group_os_versions}
        return empty_result(status='success', data=result)


api.add_resource(GroupsApi, '')
api.add_resource(GroupsApiByName, '/<string:group_name>')
api.add_resource(GroupsApiByNameOsversion, '/<string:group_name>/os_version')
