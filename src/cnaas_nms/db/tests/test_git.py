import unittest
from typing import Set, Tuple
from unittest.mock import MagicMock, patch

import pytest
from git import Repo

from cnaas_nms.app_settings import app_settings
from cnaas_nms.db.device import DeviceType
from cnaas_nms.db.git import (
    RepoType,
    _is_device_type_update_required,
    commits_out_of_sync,
    repo_checkout_working,
    repo_save_working_commit,
    template_syncstatus,
)
from cnaas_nms.db.session import redis_session


@pytest.mark.integration
class GitTests(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def requirements(self, redis):
        """Ensures the required pytest fixtures are loaded implicitly for all these tests"""
        pass

    def setUp(self) -> None:
        with redis_session() as redis:  # type: ignore
            redis.delete("SETTINGS_working_commit")
            redis.delete("TEMPLATES_working_commit")

    def tearDown(self) -> None:
        with redis_session() as redis:  # type: ignore
            redis.delete("SETTINGS_working_commit")
            redis.delete("TEMPLATES_working_commit")

    def test_check_unsync(self):
        devtypes: Set[Tuple[DeviceType, str]] = template_syncstatus({"eos/access-base.j2"})
        for devtype in devtypes:
            self.assertEqual(type(devtype[0]), DeviceType)
            self.assertEqual(type(devtype[1]), str)
        self.assertTrue((DeviceType.ACCESS, "eos") in devtypes)

    def test_is_device_type_update_required(self):
        self.assertTrue(_is_device_type_update_required({"eos/base.j2"}, ["base.j2"], "eos"))
        self.assertTrue(_is_device_type_update_required({"eos/access.j2"}, ["access*.j2"], "eos"))
        self.assertFalse(_is_device_type_update_required({"ios/base.j2"}, ["**.j2"], "eos"))
        self.assertTrue(_is_device_type_update_required({"eos/acls/some-acl.eacl"}, ["acls/*.eacl"], "eos"))
        self.assertFalse(_is_device_type_update_required({"eos/dist-base.j2"}, ["access*.j2"], "eos"))
        self.assertFalse(_is_device_type_update_required({"eos/core-base.j2"}, ["dist*.j2"], "eos"))
        self.assertFalse(_is_device_type_update_required({"junos/access-base.j2"}, ["access-*.j2"], "eos"))

    def test_savecommit(self):
        self.assertFalse(
            repo_checkout_working(RepoType.SETTINGS, dry_run=True), "Redis working commit not cleared at setUp"
        )
        self.assertFalse(
            repo_checkout_working(RepoType.TEMPLATES, dry_run=True), "Redis working commit not cleared at setUp"
        )
        repo_save_working_commit(RepoType.SETTINGS, "bd5e1f70f52037e8e2a451b2968a9ca8160a7cba")
        repo_save_working_commit(RepoType.TEMPLATES, "bd5e1f70f52037e8e2a451b2968a9ca8160a7cba")
        self.assertTrue(repo_checkout_working(RepoType.SETTINGS, dry_run=True), "Working commit not saved in redis")
        self.assertTrue(repo_checkout_working(RepoType.TEMPLATES, dry_run=True), "Working commit not saved in redis")

    def test_commits_out_of_sync(self):
        """Test commits_out_of_sync"""
        # Force template repo back one commit
        repo = Repo(app_settings.TEMPLATES_LOCAL)
        # Make sure the repo is up to date
        repo.remote().pull()
        repo.git.reset("--hard", "HEAD~1")  # Force back one step

        ahead, behind = commits_out_of_sync(RepoType.TEMPLATES)

        self.assertEqual(ahead, 0)
        self.assertEqual(behind, 1)

    @patch("cnaas_nms.db.git.Repo")
    def test_commits_out_of_sync_error(self, mock_repo):
        """Test commits_out_of_sync error"""
        mock_repo_instance = MagicMock()

        mock_repo_instance.active_branch.name.return_value = "master"

        # Some error happened in this call
        mock_repo_instance.remote.return_value.refs.__getitem__.side_effect = IndexError("this is a IndexError")

        mock_repo.return_value = mock_repo_instance

        ahead, behind = commits_out_of_sync(RepoType.TEMPLATES)

        self.assertIsNone(ahead)
        self.assertIsNone(behind)


if __name__ == "__main__":
    unittest.main()
