from flask_restx import Namespace, Resource

from cnaas_nms.api import app
from cnaas_nms.api.generic import empty_result
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.tools.security import login_required
from cnaas_nms.version import __api_version__, __version__, get_git_version

api = Namespace(
    "system", description="API for managing the CNaaS NMS API system", prefix="/api/{}".format(__api_version__)
)


class ShutdownApi(Resource):
    @login_required
    def post(self):
        print("System shutdown API called, exiting...")
        scheduler = Scheduler()
        scheduler.shutdown_mule()
        scheduler.shutdown()
        app.socketio.stop()
        exit()


class VersionApi(Resource):
    def get(self):
        git_version_str = get_git_version()
        return empty_result(status="success", data={"version": __version__, "git_version": git_version_str})


api.add_resource(ShutdownApi, "/shutdown")
api.add_resource(VersionApi, "/version")
