import shutil
import unittest

import pytest
from git import Repo

from cnaas_nms.app_settings import app_settings
from cnaas_nms.db.git_worktrees import (
    WorktreeError,
    find_templates_worktree_path,
    get_branch_folder,
    refresh_templates_worktree,
)

BRANCH = "test-branch-created-after-last-fetch"


@pytest.fixture
def origin(tmp_path, monkeypatch):
    """Set up a bare templates origin with a main branch, and point TEMPLATES_LOCAL at a path to clone it to.

    Returns a clone of origin to commit and push from."""
    origin_path = str(tmp_path / "origin.git")
    Repo.init(origin_path, bare=True)
    seed = Repo.clone_from(origin_path, str(tmp_path / "seed"))
    seed.index.commit("initial commit")
    seed.remotes.origin.push("HEAD:refs/heads/main")

    monkeypatch.setattr(app_settings, "TEMPLATES_LOCAL", str(tmp_path / "templates"))
    shutil.rmtree(get_branch_folder(BRANCH), ignore_errors=True)
    yield seed
    shutil.rmtree(get_branch_folder(BRANCH), ignore_errors=True)


def clone_templates(seed: Repo, single_branch: bool = False):
    """Clone origin into TEMPLATES_LOCAL with --depth 1, which implies --single-branch unless disabled."""
    Repo.clone_from(
        "file://" + seed.remotes.origin.url,
        app_settings.TEMPLATES_LOCAL,
        depth=1,
        branch="main",
        no_single_branch=not single_branch,
    )


def push_branch(seed: Repo) -> str:
    """Push BRANCH with a new commit to origin, returning the hexsha of its tip."""
    seed.create_head(BRANCH).checkout()
    branch_tip = seed.index.commit("branch commit").hexsha
    seed.remotes.origin.push(BRANCH)
    return branch_tip


def test_refresh_templates_worktree_fetches_new_remote_branch(origin):
    clone_templates(origin)
    # branch appears on origin only after the templates clone last fetched
    branch_tip = push_branch(origin)

    refresh_templates_worktree(BRANCH)
    worktree_path = find_templates_worktree_path(BRANCH)
    assert worktree_path
    assert Repo(worktree_path).head.commit.hexsha == branch_tip


def test_refresh_templates_worktree_reports_branch_missing_on_remote(origin):
    clone_templates(origin)

    with pytest.raises(WorktreeError, match="does not exist in the remote"):
        refresh_templates_worktree(BRANCH)


def test_refresh_templates_worktree_reports_single_branch_clone(origin):
    clone_templates(origin, single_branch=True)
    push_branch(origin)

    with pytest.raises(WorktreeError, match="only fetches .*refs/heads/main"):
        refresh_templates_worktree(BRANCH)


if __name__ == "__main__":
    unittest.main()
