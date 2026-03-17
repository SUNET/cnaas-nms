from os.path import abspath, dirname

from fastapi import APIRouter, Depends
from git import InvalidGitRepositoryError, NoSuchPathError, Repo

import cnaas_nms.version
from cnaas_nms.api.dependencies import get_current_user
from cnaas_nms.api.response import empty_result
from cnaas_nms.scheduler.scheduler import Scheduler

router = APIRouter(tags=["system"])


@router.get("/system/version")
def get_version():
    """Get the running version of CNaaS NMS."""
    version_str = cnaas_nms.version.__version__
    try:
        src_repo_path = dirname(dirname(dirname(abspath(cnaas_nms.version.__file__))))
        local_repo = Repo(src_repo_path)
        git_version_str = "Git commit {} ({})".format(
            local_repo.head.commit.name_rev, local_repo.head.commit.committed_datetime
        )
    except (InvalidGitRepositoryError, NoSuchPathError):
        git_version_str = "No git repo found"
    except Exception:
        git_version_str = "Unhandled exception"

    return empty_result(status="success", data={"version": version_str, "git_version": git_version_str})


@router.post("/system/shutdown")
def shutdown_system(user: str = Depends(get_current_user)):
    """Shutdown the CNaaS NMS system."""
    print("System shutdown API called, exiting...")
    scheduler = Scheduler()
    try:
        scheduler.shutdown_mule()
    except Exception:
        pass
    try:
        scheduler.shutdown()
    except Exception:
        pass
    return empty_result(status="success", data="Shutdown initiated")
