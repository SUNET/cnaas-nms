import os
import json
import requests
import yaml

from datetime import datetime

from flask import request
from flask_restplus import Resource, Namespace, fields
from flask_jwt_extended import jwt_required, get_jwt_identity

from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.api.generic import empty_result
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.get_apidata import get_apidata
from cnaas_nms.version import __api_version__

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
    'reboot': fields.Boolean(required=False)})


def httpd_url() -> str:
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
    del kwargs['scheduled_by']

    try:
        res = requests.post(httpd_url(), json=kwargs,
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
        url = httpd_url() + '/' + kwargs['filename']
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
    del kwargs['scheduled_by']

    try:
        url = httpd_url() + '/' + kwargs['filename']
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
    def post(self) -> dict:
        """ Download new firmware """
        json_data = request.get_json()

        kwargs = dict()

        if 'url' not in json_data:
            return empty_result(status='error',
                                data='Missing parameter urö')

        if 'sha1' not in json_data:
            return empty_result(status='error',
                                data='Missing parameter sha1')

        if 'verify_tls' not in json_data:
            return empty_result(status='error',
                                data='Missing parameter verify_tls')

        kwargs['url'] = json_data['url']
        kwargs['sha1'] = json_data['sha1']
        kwargs['verify_tls'] = json_data['verify_tls']
        kwargs['scheduled_by'] = get_jwt_identity()

        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.api.firmware:get_firmware',
            when=1,
            kwargs=kwargs)
        res = empty_result(data='Scheduled job to download firmware')
        res['job_id'] = job_id

        return res

    @jwt_required
    def get(self) -> dict:
        """ Get firmwares """
        try:
            res = requests.get(httpd_url(),
                               verify=verify_tls())
            json_data = json.loads(res.content)
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
            kwargs={'filename': filename, 'scheduled_by': get_jwt_identity()})
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
            kwargs={'filename': filename, 'scheduled_by': get_jwt_identity()})
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
        kwargs['scheduled_by'] = get_jwt_identity()

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

        if 'filename' in json_data:
            if isinstance(json_data['filename'], str):
                kwargs['filename'] = json_data['filename']
            else:
                return empty_result(status='error',
                                    data='filename should be a string')

        if 'group' in json_data:
            if isinstance(json_data['group'], str):
                kwargs['group'] = json_data['group']
            else:
                return empty_result(status='error',
                                    data='group should be a string')

        if 'hostname' in json_data:
            if isinstance(json_data['hostname'], str):
                kwargs['hostname'] = json_data['hostname']
            else:
                return empty_result(status='error',
                                    data='hostname should be a string')

        if 'start_at' in json_data:
            try:
                time_start = datetime.strptime(json_data['start_at'],
                                               date_format)
                time_now = datetime.now()

                if time_start < time_now:
                    return empty_result(status='error',
                                        data='start_at must be in the future')
                time_diff = time_start - time_now
                seconds = time_diff.seconds
            except Exception as e:
                logger.exception(f'Exception when scheduling job: {e}')
                return empty_result(status='error',
                                    data=f'Invalid date format, should be: {date_format}')

        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.confpush.firmware:device_upgrade',
            when=seconds,
            kwargs=kwargs)
        res = empty_result(data='Scheduled job to upgrade devices')
        res['job_id'] = job_id

        return res


# Firmware
api.add_resource(FirmwareApi, '')
api.add_resource(FirmwareImageApi, '/<string:filename>')
api.add_resource(FirmwareUpgradeApi, '/upgrade')
