import os
import shutil
from typing import Optional

import git.exc
from cnaas_nms.app_settings import app_settings
from cnaas_nms.tools.log import get_logger
from git import Repo


class WorktreeError(Exception):
    pass


def clean_templates_worktree():
    if os.path.isdir("/tmp/worktrees"):
        for subdir in os.listdir("/tmp/worktrees"):
            shutil.rmtree("/tmp/worktrees/" + subdir, ignore_errors=True)

    local_repo = Repo(app_settings.TEMPLATES_LOCAL)
    local_repo.git.worktree("prune")


def get_branch_folder(branch: str) -> str:
    return os.path.join("/tmp/worktrees/", branch.replace("/", "__"))


def refresh_templates_worktree(branch: str):
    """Add worktree for specified branch in separate folder"""
    logger = get_logger()
    branch_folder = get_branch_folder(branch)
    if os.path.isdir(branch_folder):
        return
    try:
        local_repo = Repo(app_settings.TEMPLATES_LOCAL)
    except git.exc.InvalidGitRepositoryError:
        logger.warning(
            "Could not add worktree for templates branch {}: templates repository is not initialized".format(branch)
        )
        return
    if not os.path.isdir("/tmp/worktrees"):
        os.mkdir("/tmp/worktrees")
    logger.debug("Adding worktree for templates branch {} in folder {}".format(branch, branch_folder))
    try:
        local_repo.git.worktree("add", branch_folder, branch)
    except git.exc.GitCommandError as e:
        logger.error("Error adding worktree for templates branch {}: {}".format(branch, e.stderr.strip()))
        raise WorktreeError(e.stderr.strip())


def find_templates_worktree_path(branch: str) -> Optional[str]:
    branch_folter = get_branch_folder(branch)
    if os.path.isdir(branch_folter):
        return branch_folter
    else:
        return None
