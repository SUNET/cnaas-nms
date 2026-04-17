from git import InvalidGitRepositoryError, NoSuchPathError

from cnaas_nms.app_settings import app_settings

__version__ = "1.9.0"
__version_info__ = tuple([field for field in __version__.split(".")])
__api_version__ = "v1.0"


def get_git_version():
    git_branch = app_settings.GIT_BRANCH
    git_commit = app_settings.GIT_COMMIT
    git_date = app_settings.GIT_DATE

    # Use environment variables if set (e.g. in CI/CD)
    if git_branch and git_commit and git_date:
        return f"Git commit {git_commit} {git_branch} ({git_date})"

    # Fallback, use local repotory if available
    try:
        from pathlib import Path

        from git import Repo

        repo = Repo(Path(__file__).resolve().parents[2])

        commit = repo.head.commit

        return f"Git commit {commit.name_rev} ({commit.committed_datetime})"

    except (InvalidGitRepositoryError, NoSuchPathError):
        return "No git repo found"
    except Exception as e:  # noqa: S110
        return f"Error retrieving git version: {e}"
