import datetime
import enum
import os
import shutil
from typing import Optional, Set, Tuple
from urllib.parse import urldefrag

import yaml
from git.exc import GitCommandError, NoSuchPathError

from cnaas_nms.app_settings import app_settings
from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.exceptions import ConfigException, RepoStructureException
from cnaas_nms.db.job import Job, JobStatus
from cnaas_nms.db.joblock import Joblock, JoblockError
from cnaas_nms.db.session import redis_session, sqla_session
from cnaas_nms.db.settings import DIR_STRUCTURE, SettingsSyntaxError, VlanConflictError, rebuild_settings_cache
from cnaas_nms.devicehandler.sync_history import add_sync_event
from cnaas_nms.tools.log import get_logger
from git import InvalidGitRepositoryError, Repo

logger = get_logger()


class RepoType(enum.Enum):
    TEMPLATES = 0
    SETTINGS = 1

    @classmethod
    def has_value(cls, value):
        return any(value == item.value for item in cls)

    @classmethod
    def has_name(cls, value):
        return any(value == item.name for item in cls)


def get_repo_status(repo_type: RepoType = RepoType.TEMPLATES) -> str:
    if repo_type == RepoType.TEMPLATES:
        local_repo_path = app_settings.TEMPLATES_LOCAL
    elif repo_type == RepoType.SETTINGS:
        local_repo_path = app_settings.SETTINGS_LOCAL
    else:
        raise ValueError("Invalid repository")

    try:
        local_repo = Repo(local_repo_path)
        return "Commit {} by {} at {}\n".format(
            local_repo.head.commit.name_rev, local_repo.head.commit.committer, local_repo.head.commit.committed_datetime
        )
    except (InvalidGitRepositoryError, NoSuchPathError):  # noqa: S110
        return "Repository is not yet cloned from remote"


def refresh_repo(repo_type: RepoType = RepoType.TEMPLATES, scheduled_by: str = None) -> str:
    """Refresh the repository for repo_type

    Args:
        repo_type: Which repository to refresh

    Returns:
        String describing what was updated.

    Raises:
        cnaas_nms.db.settings.SettingsSyntaxError
        cnaas_nms.db.joblock.JoblockError
    """
    # Acquire lock for devices to make sure no one refreshes the repository
    # while another task is building configuration for devices using repo data
    with sqla_session() as session:
        job = Job()
        job.start_job(function_name="refresh_repo", scheduled_by=scheduled_by)
        session.add(job)
        session.flush()
        job_id = job.id

        logger.info("Trying to acquire lock for devices to run refresh repo: {}".format(job_id))
        if not Joblock.acquire_lock(session, name="devices", job_id=job_id):
            raise JoblockError("Unable to acquire lock for configuring devices")
        try:
            result = _refresh_repo_task(repo_type, job_id=job_id)
            job.finish_time = datetime.datetime.utcnow()
            job.status = JobStatus.FINISHED
            job.result = {"message": result, "repository": repo_type.name}
            try:
                logger.info("Releasing lock for devices from refresh repo job: {}".format(job_id))
                Joblock.release_lock(session, job_id=job_id)
            except Exception:
                logger.error("Unable to release devices lock after refresh repo job")
            return result
        except Exception as e:
            logger.exception("Exception while scheduling job for refresh repo: {}".format(str(e)))
            job.finish_time = datetime.datetime.utcnow()
            job.status = JobStatus.EXCEPTION
            job.result = {"error": str(e), "repository": repo_type.name}
            try:
                logger.info("Releasing lock for devices from refresh repo job: {}".format(job_id))
                Joblock.release_lock(session, job_id=job_id)
            except Exception:
                logger.error("Unable to release devices lock after refresh repo job")
            raise e


def repo_chekout_working(repo_type: RepoType, dry_run: bool = False) -> bool:
    with redis_session() as redis:
        hexsha: Optional[str] = redis.get(repo_type.name + "_working_commit")
        if hexsha:
            logger.info("Trying to check out last known working commit for repo {}: {}".format(repo_type.name, hexsha))
            if dry_run:
                return True
        else:
            logger.error("Could not find previously known working commit in cache for repo: {}".format(repo_type.name))
            return False
    if repo_type == RepoType.TEMPLATES:
        local_repo_path = app_settings.TEMPLATES_LOCAL
    elif repo_type == RepoType.SETTINGS:
        local_repo_path = app_settings.SETTINGS_LOCAL
    else:
        raise ValueError("Invalid repository")

    local_repo = Repo(local_repo_path)
    local_repo.head.reference = local_repo.commit(hexsha)
    local_repo.head.reset(index=True, working_tree=True)
    return True


def repo_save_working_commit(repo_type: RepoType, hexsha: str):
    with redis_session() as redis:
        logger.info("Saving known working comit for repo {} in cache: {}".format(repo_type.name, hexsha))
        redis.set(repo_type.name + "_working_commit", hexsha)


def reset_repo(local_repo: Repo, remote_repo_path: str):
    _, branch = parse_repo_url(remote_repo_path)
    if branch:
        new_head = next(h for h in local_repo.heads if h.name == branch)
    else:
        remote_head_name = next(
            ref for ref in local_repo.remotes.origin.refs if ref.name == "origin/HEAD"
        ).ref.name.split("/")[-1]
        new_head = next(h for h in local_repo.heads if h.name == remote_head_name)

    local_repo.head.reference = new_head
    local_repo.head.reset(index=True, working_tree=True)


def _refresh_repo_task(repo_type: RepoType = RepoType.TEMPLATES, job_id: Optional[int] = None) -> str:
    """Should only be called by refresh_repo function."""
    if repo_type == RepoType.TEMPLATES:
        local_repo_path = app_settings.TEMPLATES_LOCAL
        remote_repo_path = app_settings.TEMPLATES_REMOTE
    elif repo_type == RepoType.SETTINGS:
        local_repo_path = app_settings.SETTINGS_LOCAL
        remote_repo_path = app_settings.SETTINGS_REMOTE
    else:
        raise ValueError("Invalid repository")

    ret = ""
    changed_files: Set[str] = set()
    try:
        url, branch = parse_repo_url(remote_repo_path)
        local_repo = Repo(local_repo_path)
        # If repo url has changed
        current_repo_url = next(local_repo.remotes.origin.urls)
        # Reset head if it's detached
        reset_head_failed = False
        if local_repo.head.is_detached:
            try:
                reset_repo(local_repo, remote_repo_path)
            except Exception:
                logger.exception("Git repo had detached head and repo reset failed: {}".format(remote_repo_path))
                reset_head_failed = True
        if reset_head_failed or current_repo_url != url or (branch and local_repo.head.ref.name != branch):
            if reset_head_failed:
                current_branch = "detached"  # unable to get head.ref.name if head was detached
            else:
                current_branch = local_repo.head.ref.name
            logger.info(
                "Repo URL for {} has changed from {}#{} to {}#{}, hard reset repo clone".format(
                    repo_type.name,
                    current_repo_url,
                    current_branch,
                    url,
                    branch,
                )
            )
            shutil.rmtree(local_repo_path)
            raise NoSuchPathError
        prev_commit = local_repo.commit().hexsha
        diff = local_repo.remotes.origin.pull()
        for item in diff:
            if item.ref.remote_head != local_repo.head.ref.name:
                continue

            ret += "Commit {} by {} at {}\n".format(
                item.commit.name_rev, item.commit.committer, item.commit.committed_datetime
            )
            diff_files = local_repo.git.diff("{}..{}".format(prev_commit, item.commit.hexsha), name_only=True).split()
            changed_files.update(diff_files)
            prev_commit = item.commit.hexsha
    except (InvalidGitRepositoryError, NoSuchPathError):  # noqa: S110
        logger.info("Local repository {} not found, cloning from remote".format(local_repo_path))
        try:
            local_repo = Repo.clone_from(url, local_repo_path, branch=branch)
        except (InvalidGitRepositoryError, NoSuchPathError) as e:
            raise ConfigException("Invalid remote repository {}: {}".format(remote_repo_path, str(e)))
        except GitCommandError as e:
            raise ConfigException("Error cloning remote repository {}: {}".format(remote_repo_path, str(e)))

        ret = "Cloned new from remote. Last commit {} by {} at {}".format(
            local_repo.head.commit.name_rev, local_repo.head.commit.committer, local_repo.head.commit.committed_datetime
        )

    if repo_type == RepoType.SETTINGS:
        try:
            rebuild_settings_cache()
        except SettingsSyntaxError as e:
            logger.error("Error in settings repo configuration: {}".format(e))
            if repo_chekout_working(repo_type):
                rebuild_settings_cache()
            raise e
        except VlanConflictError as e:
            logger.error("VLAN conflict in repo configuration: {}".format(e))
            if repo_chekout_working(repo_type):
                rebuild_settings_cache()
            raise e
        else:
            try:
                repo_save_working_commit(repo_type, local_repo.head.commit.hexsha)
            except Exception as e:  # noqa: F401
                logger.error("Could not save last working commit: {}".format(e))
        logger.debug("Files changed in settings repository: {}".format(changed_files))
        updated_devtypes, updated_hostnames = settings_syncstatus(updated_settings=changed_files)
        logger.debug(
            "Devicestypes to be marked unsynced after repo refresh: {}".format(
                ", ".join([dt.name for dt in updated_devtypes])
            )
        )
        logger.debug("Devices to be marked unsynced after repo refresh: {}".format(", ".join(updated_hostnames)))
        with sqla_session() as session:
            devtype: DeviceType
            for devtype in updated_devtypes:
                Device.set_devtype_syncstatus(session, devtype, ret, "settings", job_id=job_id)
            for hostname in updated_hostnames:
                dev: Device = session.query(Device).filter(Device.hostname == hostname).one_or_none()
                if dev:
                    dev.synchronized = False
                    add_sync_event(hostname, "refresh_settings", ret, job_id)
                else:
                    logger.warn("Settings updated for unknown device: {}".format(hostname))

    if repo_type == RepoType.TEMPLATES:
        logger.debug("Files changed in template repository: {}".format(changed_files))
        updated_devtypes = template_syncstatus(updated_templates=changed_files)
        updated_list = ["{}:{}".format(platform, dt.name) for dt, platform in updated_devtypes]
        logger.debug("Devicestypes to be marked unsynced after repo refresh: {}".format(", ".join(updated_list)))
        with sqla_session() as session:
            devtype: DeviceType
            for devtype, platform in updated_devtypes:
                Device.set_devtype_syncstatus(session, devtype, ret, "templates", platform, job_id)

    return ret


def template_syncstatus(updated_templates: set) -> Set[Tuple[DeviceType, str]]:
    """Determine what device types have become unsynchronized because
    of updated template files."""
    unsynced_devtypes = set()
    local_repo_path = app_settings.TEMPLATES_LOCAL

    # loop through OS/platform types
    for platform in os.listdir(local_repo_path):
        path = os.path.join(local_repo_path, platform)
        if not os.path.isdir(path) or platform.startswith("."):
            continue

        mapfile = os.path.join(path, "mapping.yml")
        if not os.path.isfile(mapfile):
            raise RepoStructureException("File mapping.yml not found in template repo {}".format(path))
        try:
            with open(mapfile, "r") as f:
                mapping = yaml.safe_load(f)
        except Exception as e:
            logger.exception("Could not parse {}/mapping.yml in template repo: {}".format(path, str(e)))
            raise RepoStructureException("Could not parse {}/mapping.yml in template repo: {}".format(path, str(e)))

        devtype: DeviceType
        for devtype in DeviceType:
            if devtype.name in mapping:
                update_required = False
                try:
                    dependencies = list([mapping[devtype.name]["entrypoint"]])
                    if "dependencies" in mapping[devtype.name] and isinstance(
                        mapping[devtype.name]["dependencies"], list
                    ):
                        dependencies.extend(mapping[devtype.name]["dependencies"])
                except KeyError as e:
                    logger.exception(
                        "Could not parse mapping.yml in template repo for {}, value not found: {}".format(
                            devtype.name, str(e)
                        )
                    )
                    raise RepoStructureException(
                        "Could not parse mapping.yml in template repo for {}, value not found: {}".format(
                            devtype.name, str(e)
                        )
                    )

                for dependency in dependencies:
                    if os.path.join(platform, dependency) in updated_templates:
                        update_required = True
                if update_required:
                    logger.info("Template for device type {} has been updated".format(devtype.name))
                    unsynced_devtypes.add((devtype, platform))

    return unsynced_devtypes


def settings_syncstatus(updated_settings: set) -> Tuple[Set[DeviceType], Set[str]]:
    """Determine what devices has become unsynchronized after updating
    the settings repository."""
    unsynced_devtypes = set()
    unsynced_hostnames = set()
    filename: str
    for filename in updated_settings:
        basedir = filename.split(os.path.sep)[0]
        if basedir not in DIR_STRUCTURE:
            continue
        if basedir.startswith("global"):
            return {DeviceType.ACCESS, DeviceType.DIST, DeviceType.CORE}, set()
        elif basedir.startswith("fabric"):
            unsynced_devtypes.update({DeviceType.DIST, DeviceType.CORE})
        elif basedir.startswith("access"):
            unsynced_devtypes.add(DeviceType.ACCESS)
        elif basedir.startswith("dist"):
            unsynced_devtypes.add(DeviceType.DIST)
        elif basedir.startswith("core"):
            unsynced_devtypes.add(DeviceType.CORE)
        elif basedir.startswith("devices"):
            try:
                hostname = filename.split(os.path.sep)[1]
                if Device.valid_hostname(hostname):
                    unsynced_hostnames.add(hostname)
            except Exception as e:
                logger.exception("Error in settings devices directory: {}".format(str(e)))
        else:
            logger.warn("Unhandled settings file found {}, syncstatus not updated".format(filename))
    return (unsynced_devtypes, unsynced_hostnames)


def parse_repo_url(url: str) -> Tuple[str, Optional[str]]:
    """Parses a URL to a repository, returning the path and branch refspec separately"""
    path, branch = urldefrag(url)
    return path, branch if branch else None
