from flask_restful import Resource
from flask import render_template
from cnaas_nms.api.device import DevicesApi
from cnaas_nms.api.jobs import JobsApi


class Status(Resource):
    @classmethod
    def jobs(cls):
        jobs = JobsApi()
        jobdata = jobs.get()
        return render_template('jobs.html', jobs=jobdata['data']['jobs'])

    @classmethod
    def devices(cls):
        devices = DevicesApi()
        devicesdata = devices.get()
        return render_template('devices.html', devices=devicesdata[0]['data']['devices'])
