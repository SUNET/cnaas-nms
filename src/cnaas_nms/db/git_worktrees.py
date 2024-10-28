import os
import shutil
from typing import List, Optional

import git.exc
from cnaas_nms.app_settings import app_settings
from cnaas_nms.db.device import Device
from cnaas_nms.db.groups import get_groups_using_branch
from cnaas_nms.db.session import sqla_session
from cnaas_nms.devicehandler.sync_history import add_sync_event
from cnaas_nms.tools.log import get_logger
from git import Repo


class WorktreeError(Exception):
    pass


def refresh_existing_templates_worktrees(by: str, job_id: int, group_settings: dict, device_primary_groups: dict):
    """Look for existing worktrees and refresh them"""
    logger = get_logger()
    updated_groups: List[str] = []
    if os.path.isdir("/tmp/worktrees"):
        for subdir in os.listdir("/tmp/worktrees"):
            try:
                logger.info("Pulling worktree for branch {}".format(subdir))
                wt_repo = Repo("/tmp/worktrees/" + subdir)
                diff = wt_repo.remotes.origin.pull()
                if not diff:
                    continue
            except Exception as e:
                logger.exception(e)
                shutil.rmtree("/tmp/worktrees/" + subdir, ignore_errors=True)
            updated_groups.append(get_groups_using_branch(subdir, group_settings))

    # find all devices that are using these branches and mark them as unsynchronized
    updated_hostnames: List[str] = []
    with sqla_session() as session:
        for hostname, primary_group in device_primary_groups:
            if hostname in updated_hostnames:
                continue
            if primary_group in updated_groups:
                dev: Device = session.query(Device).filter_by(hostname=hostname).one_or_none()
                if dev:
                    dev.synchronized = False
                    add_sync_event(hostname, "refresh_templates", by, job_id)
                    updated_hostnames.append(hostname)
    logger.debug(
        "Devices marked as unsynchronized because git worktree branches were refreshed: {}".format(
            ", ".join(updated_hostnames)
        )
    )

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
        local_repo.git.worktree("prune")
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
