from flask import request
from flask_restplus import Resource, Namespace, fields
from flask_jwt_extended import jwt_required

from cnaas_nms.api.generic import empty_result
from cnaas_nms.api import app
from cnaas_nms.version import __api_version__


api = Namespace('system', description='API for managing the CNaaS NMS API system',
                prefix='/api/{}'.format(__api_version__))


class ShutdownApi(Resource):
    @jwt_required
    def post(self):
        print("System shutdown API called, exiting...")
        app.socketio.stop()
        exit()


api.add_resource(ShutdownApi, '/shutdown')
