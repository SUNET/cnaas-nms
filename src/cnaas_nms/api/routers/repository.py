from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cnaas_nms.api.dependencies import get_current_user
from cnaas_nms.api.response import CnaasJSONResponse, empty_result
from cnaas_nms.db.git import RepoType, get_repo_status, refresh_repo
from cnaas_nms.db.joblock import JoblockError
from cnaas_nms.db.settings import SettingsSyntaxError, VerifyPathException

router = APIRouter(tags=["repository"])


class RepositoryAction(BaseModel):
    action: str


@router.get("/repository/{repo}")
def get_repository(repo: str, user: str = Depends(get_current_user)):
    """Get repository information."""
    try:
        repo_type = RepoType[str(repo).upper()]
    except Exception:
        return CnaasJSONResponse(status_code=400, content=empty_result("error", "Invalid repository type"))
    return empty_result("success", get_repo_status(repo_type))


@router.put("/repository/{repo}")
def modify_repository(repo: str, repo_action: RepositoryAction, user: str = Depends(get_current_user)):
    """Modify repository."""
    try:
        repo_type = RepoType[str(repo).upper()]
    except Exception:
        return CnaasJSONResponse(status_code=400, content=empty_result("error", "Invalid repository type"))

    if str(repo_action.action).upper() == "REFRESH":
        try:
            res = refresh_repo(repo_type, user)
            return empty_result("success", res)
        except VerifyPathException as e:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result("error", "Repository structure is invalid ({}): {}".format(type(e).__name__, str(e))),
            )
        except JoblockError as e:
            return CnaasJSONResponse(
                status_code=503,
                content=empty_result(
                    "error",
                    "Another job is locking configuration of devices, try again later ({})".format(str(e)),
                ),
            )
        except SettingsSyntaxError as e:
            return CnaasJSONResponse(
                status_code=400,
                content=empty_result("error", "Syntax error in repository: {}".format(str(e))),
            )
        except Exception as e:
            return CnaasJSONResponse(
                status_code=500,
                content=empty_result("error", "Error in repository: {}".format(str(e))),
            )
    else:
        return CnaasJSONResponse(status_code=400, content=empty_result("error", "Invalid action"))
