import os
import json
import requests

from datetime import datetime
from typing import Optional

from flask import request, make_response
from flask_restx import Resource, Namespace, fields
from flask_jwt_extended import jwt_required, get_jwt_identity

from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.api.generic import empty_result
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.get_apidata import get_apidata
from cnaas_nms.version import __api_version__
from cnaas_nms.confpush.nornir_helper import cnaas_init, inventory_selector
from cnaas_nms.db.device import Device
from cnaas_nms.db.settings import get_groups

logger = get_logger()


api = Namespace('firmware', description='API for handling firmwares',
                prefix='/api/{}'.format(__api_version__))

firmware_model = api.model('firmware_download', {
    'url': fields.String(required=True),
    'sha1': fields.String(required=True),
    'verify_tls': fields.Boolean(required=False),
    'filename': fields.String(required=True)})

firmware_upgrade_model = api.model('firmware_upgrade', {
    'url': fields.String(required=True),
    'start_at': fields.String(required=False),
    'download': fields.Boolean(required=False),
    'activate': fields.Boolean(required=False),
    'filename': fields.String(required=False),
    'group': fields.String(required=False),
    'hostname': fields.String(required=False),
    'pre_flight': fields.Boolean(required=False),
    'post_flight': fields.Boolean(required=False),
    'post_wattime': fields.Integer(required=False),
    'reboot': fields.Boolean(required=False)})


def get_httpd_url() -> str:
    apidata = get_apidata()
    httpd_url = 'https://cnaas_httpd/api/v1.0/firmware'
    if isinstance(apidata, dict) and 'httpd_url' in apidata:
        httpd_url = apidata['httpd_url']
    return httpd_url


def verify_tls() -> bool:
    verify_tls = True
    apidata = get_apidata()
    if isinstance(apidata, dict) and 'verify_tls' in apidata:
        verify_tls = apidata['verify_tls']
    return verify_tls


@job_wrapper
def get_firmware(**kwargs: dict) -> str:
    try:
        res = requests.post(get_httpd_url(), json=kwargs,
                            verify=verify_tls())
        json_data = json.loads(res.content)
    except Exception as e:
        logger.exception(f"Exception while getting firmware: {e}")
        return 'Could not download firmware: ' + str(e)
    if json_data['status'] == 'error':
        return json_data['message']
    return 'File downloaded from: ' + kwargs['url']


@job_wrapper
def get_firmware_chksum(**kwargs: dict) -> str:
    try:
        url = get_httpd_url() + '/' + kwargs['filename']
        res = requests.get(url, verify=verify_tls())
        json_data = json.loads(res.content)
    except Exception as e:
        logger.exception(f"Exceptionb while getting checksum: {e}")
        return 'Failed to get checksum for ' + kwargs['filename']
    if json_data['status'] == 'error':
        return json_data['message']
    return json_data['data']['file']['sha1']


@job_wrapper
def remove_file(**kwargs: dict) -> str:
    try:
        url = get_httpd_url() + '/' + kwargs['filename']
        res = requests.delete(url, verify=verify_tls())
        json_data = json.loads(res.content)
    except Exception as e:
        logger.exception(f"Exception when removing firmware: {e}")
        return 'Failed to remove file'
    if json_data['status'] == 'error':
        return 'Failed to remove file ' + kwargs['filename']
    return 'File ' + kwargs['filename'] + ' removed'


class FirmwareApi(Resource):
    @jwt_required
    @api.expect(firmware_model)
    def post(self) -> tuple:
        """ Download new firmware """
        json_data = request.get_json()

        kwargs = dict()

        if 'url' not in json_data:
            return empty_result(status='error',
                                data='Missing parameter url')

        if 'sha1' not in json_data:
            return empty_result(status='error',
                                data='Missing parameter sha1')

        if 'verify_tls' not in json_data:
            return empty_result(status='error',
                                data='Missing parameter verify_tls')

        kwargs['url'] = json_data['url']
        kwargs['sha1'] = json_data['sha1']
        kwargs['verify_tls'] = json_data['verify_tls']

        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.api.firmware:get_firmware',
            when=1,
            scheduled_by=get_jwt_identity(),
            kwargs=kwargs)
        res = empty_result(data='Scheduled job to download firmware')
        res['job_id'] = job_id

        return res

    @jwt_required
    def get(self) -> tuple:
        """ Get firmwares """
        try:
            res = requests.get(get_httpd_url(),
                               verify=verify_tls())
            json_data = json.loads(res.content)['data']
        except Exception as e:
            logger.exception(f"Exception when getting images: {e}")
            return empty_result(status='error',
                                data='Could not get files'), 404
        return empty_result(status='success', data=json_data)


class FirmwareImageApi(Resource):
    @jwt_required
    def get(self, filename: str) -> dict:
        """ Get information about a single firmware """
        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.api.firmware:get_firmware_chksum',
            when=1,
            scheduled_by=get_jwt_identity(),
            kwargs={'filename': filename})
        res = empty_result(data='Scheduled job get firmware information')
        res['job_id'] = job_id

        return res

    @jwt_required
    def delete(self, filename: str) -> dict:
        """ Remove firmware """
        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.api.firmware:remove_file',
            when=1,
            scheduled_by=get_jwt_identity(),
            kwargs={'filename': filename})
        res = empty_result(data='Scheduled job to remove firmware')
        res['job_id'] = job_id

        return res


class FirmwareUpgradeApi(Resource):
    def firmware_url(self) -> str:
        apidata = get_apidata()
        httpd_url = ''
        if isinstance(apidata, dict) and 'firmware_url' in apidata:
            httpd_url = apidata['firmware_url']
        elif 'FIRMWARE_URL' in os.environ:
            httpd_url = os.environ['FIRMWARE_URL']
        return httpd_url

    @jwt_required
    @api.expect(firmware_upgrade_model)
    def post(self):
        """ Upgrade firmware on device """
        json_data = request.get_json()

        kwargs = dict()
        seconds = 1
        date_format = "%Y-%m-%d %H:%M:%S"
        url = self.firmware_url()

        if 'url' not in json_data and url == '':
            return empty_result(status='error',
                                data='No external address configured for '
                                'HTTPD, please specify one with "url"')

        if 'url' not in json_data:
            kwargs['url'] = url
        else:
            if isinstance(json_data['url'], str):
                kwargs['url'] = json_data['url']
            else:
                return empty_result(status='error',
                                    data='url should be a string')

        if 'activate' in json_data:
            if isinstance(json_data['activate'], bool):
                kwargs['activate'] = json_data['activate']
            else:
                return empty_result(status='error',
                                    data='activate should be a boolean')

        if 'download' in json_data:
            if isinstance(json_data['download'], bool):
                kwargs['download'] = json_data['download']
            else:
                return empty_result(status='error',
                                    data='download should be a boolean')

        if 'reboot' in json_data:
            if isinstance(json_data['reboot'], bool):
                kwargs['reboot'] = json_data['reboot']
            else:
                return empty_result(status='error',
                                    data='reboot should be a boolean')

        if 'pre_flight' in json_data:
            if isinstance(json_data['pre_flight'], bool):
                kwargs['pre_flight'] = json_data['pre_flight']
            else:
                return empty_result(status='error',
                                    data='pre_flight should be a boolean')

        if 'post_flight' in json_data:
            if isinstance(json_data['post_flight'], bool):
                kwargs['post_flight'] = json_data['post_flight']
            else:
                return empty_result(status='error',
                                    data='post_flight should be a boolean')

        if 'post_waittime' in json_data:
            if isinstance(json_data['post_waittime'], int):
                kwargs['post_waittime'] = json_data['post_waittime']
            else:
                return empty_result(status='error',
                                    data='post_waittime should be an integer')

        if 'filename' in json_data:
            if isinstance(json_data['filename'], str):
                kwargs['filename'] = json_data['filename']
            else:
                return empty_result(status='error',
                                    data='filename should be a string')

        total_count: Optional[int] = None
        nr = cnaas_init()

        if 'hostname' in json_data:
            hostname = str(json_data['hostname'])
            if not Device.valid_hostname(hostname):
                return empty_result(
                    status='error',
                    data=f"Hostname '{hostname}' is not a valid hostname"
                ), 400
            _, total_count, _ = inventory_selector(nr, hostname=hostname)
            if total_count != 1:
                return empty_result(
                    status='error',
                    data=f"Hostname '{hostname}' not found or is not a managed device"
                ), 400
            kwargs['hostname'] = hostname
        elif 'group' in json_data:
            group_name = str(json_data['group'])
            if group_name not in get_groups():
                return empty_result(status='error', data='Could not find a group with name {}'.format(group_name))
            kwargs['group'] = group_name
            _, total_count, _ = inventory_selector(nr, group=group_name)
            kwargs['group'] = group_name
        else:
            return empty_result(
                status='error',
                data=f"No devices to upgrade were specified"
            ), 400

        if 'comment' in json_data and isinstance(json_data['comment'], str):
            kwargs['job_comment'] = json_data['comment']
        if 'ticket_ref' in json_data and isinstance(json_data['ticket_ref'], str):
            kwargs['job_ticket_ref'] = json_data['ticket_ref']

        if 'start_at' in json_data:
            try:
                time_start = datetime.strptime(json_data['start_at'],
                                               date_format)
                time_now = datetime.utcnow()

                if time_start < time_now:
                    return empty_result(status='error',
                                        data='start_at must be in the future')
                time_diff = time_start - time_now
                seconds = int(time_diff.total_seconds())
            except Exception as e:
                logger.exception(f'Exception when scheduling job: {e}')
                return empty_result(status='error',
                                    data=f'Invalid date format, should be: {date_format}')

        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.firmware:device_upgrade',
            when=seconds,
            scheduled_by=get_jwt_identity(),
            kwargs=kwargs)
        res = empty_result(data='Scheduled job to upgrade devices')
        res['job_id'] = job_id

        resp = make_response(json.dumps(res), 200)
        if total_count:
            resp.headers['X-Total-Count'] = total_count
        resp.headers['Content-Type'] = "application/json"
        return resp


# Firmware
api.add_resource(FirmwareApi, '')
api.add_resource(FirmwareImageApi, '/<string:filename>')
api.add_resource(FirmwareUpgradeApi, '/upgrade')
