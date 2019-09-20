import os
import json
import requests

from flask import request
from flask_restful import Resource
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.api.generic import empty_result
from cnaas_nms.scheduler.wrapper import job_wrapper


if 'HTTPD_HOSTNAME' not in os.environ:
    URL = 'https://cnaas_httpd/api/v1.0/firmware'
else:
    URL = os.environ['HTTPD_HOSTNAME']


@job_wrapper
def get_firmware(**kwargs: dict) -> str:
    try:
        res = requests.post(URL, json=kwargs,
                            verify=False)
        json_data = json.loads(res.content)
    except Exception:
        return 'Could not parse result from firmware fetch'
    if 'message' in json_data:
        return json_data['message']
    return 'File downloaded from: ' + kwargs['url']


@job_wrapper
def get_firmware_chksum(**kwargs: dict) -> str:
    try:
        url = URL + '/' + kwargs['filename']
        res = requests.get(url, verify=False)
        json_data = json.loads(res.content)
    except Exception:
        return 'Failed to get file'
    return json_data['data']['file']['sha1']


@job_wrapper
def remove_file(**kwargs: dict) -> str:
    try:
        url = URL + '/' + kwargs['filename']
        res = requests.delete(url, verify=False)
        json_data = json.loads(res.content)
    except Exception:
        return 'Failed to remove file'
    if json_data['status'] == 'error':
        return 'Failed to remove file ' + kwargs['filename']
    return 'File ' + kwargs['filename'] + ' removed'


class FirmwareApi(Resource):
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

    def get(self) -> dict:
        try:
            res = requests.get('https://localhost/api/v1.0/firmware',
                               verify=False)
            json_data = json.loads(res.content)
        except Exception:
            return empty_result(status='error',
                                data='Could not get files'), 404
        return empty_result(status='success', data=json_data)


class FirmwareImageApi(Resource):
    def get(self, filename: str) -> dict:
        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.api.firmware:get_firmware_chksum',
            when=1,
            kwargs={'filename': filename})
        res = empty_result(data='Scheduled job get firmware information')
        res['job_id'] = job_id

        return res

    def delete(self, filename: str) -> dict:
        scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            'cnaas_nms.api.firmware:remove_file',
            when=1,
            kwargs={'filename': filename})
        res = empty_result(data='Scheduled job to remove firmware')
        res['job_id'] = job_id

        return res
