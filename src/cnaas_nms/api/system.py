from os.path import dirname, abspath
from flask_restx import Resource, Namespace
from flask_jwt_extended import jwt_required
from git import Repo
from git import InvalidGitRepositoryError, NoSuchPathError

from cnaas_nms.api.generic import empty_result
from cnaas_nms.api import app
import cnaas_nms.version
from cnaas_nms.version import __api_version__


api = Namespace('system', description='API for managing the CNaaS NMS API system',
                prefix='/api/{}'.format(__api_version__))


class ShutdownApi(Resource):
    @jwt_required()
    def post(self):
        print("System shutdown API called, exiting...")
        app.socketio.stop()
        exit()


class VersionApi(Resource):
    def get(self):
        version_str = cnaas_nms.version.__version__
        try:
            src_repo_path = dirname(dirname(dirname(abspath(cnaas_nms.version.__file__))))
            local_repo = Repo(src_repo_path)
            git_version_str = 'Git commit {} ({})'.format(
                local_repo.head.commit.name_rev,
                local_repo.head.commit.committed_datetime
            )
        except (InvalidGitRepositoryError, NoSuchPathError) as e:
            git_version_str = 'No git repo found'
        except Exception:
            git_version_str = 'Unhandled exception'

        return empty_result(status='success', data={
            "version": version_str,
            "git_version": git_version_str
        })


api.add_resource(ShutdownApi, '/shutdown')
api.add_resource(VersionApi, '/version')
