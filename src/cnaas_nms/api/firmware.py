import os
import json
import requests
import yaml

from datetime import datetime

from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required

from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.api.generic import empty_result
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.get_apidata import get_apidata

logger = get_logger()


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
    def post(self) -> dict:
        json_data = request.get_json()
        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.api.firmware:get_firmware',
            when=1,
            kwargs=json_data)
        res = empty_result(data='Scheduled job to download firmware')
        res['job_id'] = job_id

        return res

    @jwt_required
    def get(self) -> dict:
        try:
            res = requests.get(httpd_url() + 'firmware',
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
        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.api.firmware:get_firmware_chksum',
            when=1,
            kwargs={'filename': filename})
        res = empty_result(data='Scheduled job get firmware information')
        res['job_id'] = job_id

        return res

    @jwt_required
    def delete(self, filename: str) -> dict:
        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.api.firmware:remove_file',
            when=1,
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
        return httpd_url

    @jwt_required
    def post(self):
        json_data = request.get_json()
        seconds = 1
        date_format = "%Y-%m-%d %H:%M:%S"
        url = self.firmware_url()

        if 'url' in json_data:
            url = json_data['url']
        elif url == '':
            return empty_result(status='error',
                                data='No external address configured for HTTPD, please specify one with "url"')

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
            kwargs=json_data)
        res = empty_result(data='Scheduled job to upgrade devices')
        res['job_id'] = job_id

        return res
