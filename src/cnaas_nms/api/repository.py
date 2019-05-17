from flask import request
from flask_restful import Resource

from cnaas_nms.db.git import RepoType, refresh_repo, get_repo_status
from cnaas_nms.db.settings import VerifyPathException
from cnaas_nms.api.generic import empty_result


class RepositoryApi(Resource):
    def get(self, repo):
        try:
            repo_type = RepoType[str(repo).upper()]
        except:
            return empty_result('error', "Invalid repository type"), 400
        return empty_result('success', get_repo_status(repo_type))


    def put(self, repo):
        json_data = request.get_json()
        try:
            repo_type = RepoType[str(repo).upper()]
        except:
            return empty_result('error', "Invalid repository type"), 400

        if 'action' in json_data:
            if str(json_data['action']).upper() == 'REFRESH':
                # TODO: consider doing as scheduled job?
                try:
                    res = refresh_repo(repo_type)
                    return empty_result('success', res)
                except VerifyPathException as e:
                    return empty_result(
                        'error',
                        "Repository structure is invalid: {}".format(type(e).__name__, str(e))
                    )

            else:
                return empty_result('error', "Invalid action"), 400
        else:
            return empty_result('error', "No action specified"), 400

