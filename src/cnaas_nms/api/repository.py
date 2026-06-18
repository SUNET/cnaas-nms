from flask import request
from flask_restx import Namespace, Resource, fields

from cnaas_nms.api.generic import empty_result
from cnaas_nms.db.git import RepoType, commits_out_of_sync, get_repo_status, refresh_repo
from cnaas_nms.db.joblock import JoblockError
from cnaas_nms.db.settings import SettingsSyntaxError, VerifyPathException
from cnaas_nms.tools.security import get_identity, login_required
from cnaas_nms.version import __api_version__

api = Namespace("repository", description="API for handling repositories", prefix="/api/{}".format(__api_version__))

repository_model = api.model(
    "repository",
    {
        "action": fields.String(required=True, example="REFRESH"),
    },
)

repository_return_model = api.model(
    "RepositoryReturn",
    {
        "status": fields.String(enum=["success", "error"], description="Status of the response"),
        "data": fields.String(description="Commit information"),
        "commits_ahead": fields.Integer(
            description="How many commits ahead of origin",
            required=False,
            default=None,
        ),
        "commits_behind": fields.Integer(
            description="How many commits behind of origin",
            required=False,
            default=None,
        ),
    },
)


class RepositoryApi(Resource):
    @api.doc(
        params={
            "repo": {
                "description": "Repository type",
                "type": "string",
                "enum": [r.name.lower() for r in RepoType],
            }
        }
    )
    @api.marshal_with(repository_return_model)
    @login_required
    def get(self, repo: str):
        """Get repository information"""
        try:
            repo_type = RepoType[str(repo).upper()]
        except Exception:  # noqa: S110
            return empty_result("error", "Invalid repository type"), 400
        result = empty_result("success", get_repo_status(repo_type))

        ahead, behind = commits_out_of_sync(repo_type)
        result["commits_ahead"] = ahead
        result["commits_behind"] = behind

        return result

    @login_required
    @api.expect(repository_model)
    def put(self, repo):
        """Modify repository"""
        json_data = request.get_json()
        try:
            repo_type = RepoType[str(repo).upper()]
        except Exception:  # noqa: T001
            return empty_result("error", "Invalid repository type"), 400

        if "action" in json_data:
            if str(json_data["action"]).upper() == "REFRESH":
                # TODO: consider doing as scheduled job?
                try:
                    res = refresh_repo(repo_type, get_identity())
                    return empty_result("success", res)
                except VerifyPathException as e:
                    return (
                        empty_result(
                            "error", "Repository structure is invalid ({}): {}".format(type(e).__name__, str(e))
                        ),
                        400,
                    )
                except JoblockError as e:
                    return (
                        empty_result(
                            "error",
                            "Another job is locking configuration of devices, try again later ({})".format(str(e)),
                        ),
                        503,
                    )
                except SettingsSyntaxError as e:
                    return empty_result("error", "Syntax error in repository: {}".format(str(e))), 400
                except Exception as e:
                    return empty_result("error", "Error in repository: {}".format(str(e))), 500
            else:
                return empty_result("error", "Invalid action"), 400
        else:
            return empty_result("error", "No action specified"), 400


api.add_resource(RepositoryApi, "/<string:repo>")
