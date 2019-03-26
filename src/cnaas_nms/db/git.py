from git import Repo
from git import InvalidGitRepositoryError, NoSuchPathError
from git.exc import NoSuchPathError
import yaml

from cnaas_nms.db.exceptions import ConfigException
from cnaas_nms.tools.log import get_logger

logger = get_logger()


def refresh_repo(repo_type: str = 'templates') -> str:
    """Refresh the repository for repo_type

    Args:
        repo_type: can be either 'templates' or 'settings'

    Returns:
        String describing what was updated.
    """

    with open('/etc/cnaas-nms/repository.yml', 'r') as db_file:
        repo_config = yaml.safe_load(db_file)

    if repo_type == 'templates':
        local_repo_path = repo_config['templates_local']
        remote_repo_path = repo_config['templates_remote']
    elif repo_type == 'settings':
        local_repo_path = repo_config['settings_local']
        remote_repo_path = repo_config['settings_remote']
    else:
        raise ValueError("Invalid repository")

    ret = ''
    try:
        local_repo = Repo(local_repo_path)
        diff = local_repo.remotes.origin.pull()
        for item in diff:
            ret += 'Commit {} by {} at {}\n'.format(
                item.commit.name_rev,
                item.commit.committer,
                item.commit.committed_datetime
            )
    except (InvalidGitRepositoryError, NoSuchPathError) as e:
        logger.info("Local repository {} not found, cloning from remote".\
                    format(local_repo_path))
        try:
            remote_repo = Repo(remote_repo_path)
        except NoSuchPathError as e:
            raise ConfigException("Invalid remote repository {}: {}".format(
                remote_repo_path,
                str(e)
            ))

        remote_repo.clone(local_repo_path)
        local_repo = Repo(local_repo_path)
        ret = 'Cloned new from remote. Last commit {} by {} at {}'.format(
            local_repo.head.commit.name_rev,
            local_repo.head.commit.committer,
            local_repo.head.commit.committed_datetime
        )

    return ret



