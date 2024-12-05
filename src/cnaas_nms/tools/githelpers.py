from typing import List, Set, Tuple

import git.remote
from git import Repo


def parse_git_changed_files(
    diff: List[git.remote.FetchInfo], prev_commit: str, local_repo: Repo
) -> Tuple[str, Set[str]]:
    ret_msg = ""
    changed_files: Set[str] = set()
    for item in diff:
        if item.ref.remote_head != local_repo.head.ref.name:  # type: ignore[attr-defined]
            continue

        ret_msg += "Commit {} by {} at {}\n".format(
            item.commit.name_rev, item.commit.committer, item.commit.committed_datetime
        )
        diff_files = local_repo.git.diff("{}..{}".format(prev_commit, item.commit.hexsha), name_only=True).split()
        changed_files.update(diff_files)
        prev_commit = item.commit.hexsha
    return ret_msg, changed_files
