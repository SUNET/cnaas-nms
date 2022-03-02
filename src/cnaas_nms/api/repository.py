from flask import request
from flask_restx import Resource, Namespace, fields
from flask_jwt_extended import jwt_required, get_jwt_identity

from cnaas_nms.db.git import RepoType, refresh_repo, get_repo_status
from cnaas_nms.db.settings import VerifyPathException, SettingsSyntaxError
from cnaas_nms.api.generic import empty_result
from cnaas_nms.db.joblock import JoblockError
from cnaas_nms.version import __api_version__


api = Namespace('repository', description='API for handling repositories',
                prefix='/api/{}'.format(__api_version__))

repository_model = api.model('repository', {
    'action': fields.String(required=True),
})


class RepositoryApi(Resource):
    @jwt_required()
    def get(self, repo):
        """ Get repository information """
        try:
            repo_type = RepoType[str(repo).upper()]
        except:
            return empty_result('error', "Invalid repository type"), 400
        return empty_result('success', get_repo_status(repo_type))

    @jwt_required()
    @api.expect(repository_model)
    def put(self, repo):
        """ Modify repository """
        json_data = request.get_json()
        try:
            repo_type = RepoType[str(repo).upper()]
        except:
            return empty_result('error', "Invalid repository type"), 400

        if 'action' in json_data:
            if str(json_data['action']).upper() == 'REFRESH':
                # TODO: consider doing as scheduled job?
                try:
                    res = refresh_repo(repo_type, get_jwt_identity())
                    return empty_result('success', res)
                except VerifyPathException as e:
                    return empty_result(
                        'error',
                        "Repository structure is invalid ({}): {}".format(type(e).__name__, str(e))
                    ), 400
                except JoblockError as e:
                    return empty_result(
                        'error',
                        "Another job is locking configuration of devices, try again later ({})".format(str(e))
                    ), 503
                except SettingsSyntaxError as e:
                    return empty_result(
                        'error',
                        "Syntax error in repository: {}".format(str(e))
                    ), 400
                except Exception as e:
                    return empty_result(
                        'error',
                        "Error in repository: {}".format(str(e))
                    ), 500
            else:
                return empty_result('error', "Invalid action"), 400
        else:
            return empty_result('error', "No action specified"), 400


api.add_resource(RepositoryApi, '/<string:repo>')
