import unittest

import pytest

from cnaas_nms.db.git import template_syncstatus, repo_save_working_commit, \
    repo_chekout_working, RepoType
from cnaas_nms.db.device import DeviceType
from cnaas_nms.db.session import redis_session


@pytest.mark.integration
class GitTests(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def requirements(self, redis):
        """Ensures the required pytest fixtures are loaded implicitly for all these tests"""
        pass

    def setUp(self) -> None:
        with redis_session() as redis:
            redis.delete("SETTINGS_working_commit")
            redis.delete("TEMPLATES_working_commit")

    def tearDown(self) -> None:
        with redis_session() as redis:
            redis.delete("SETTINGS_working_commit")
            redis.delete("TEMPLATES_working_commit")

    def test_check_unsync(self):
        devtypes = template_syncstatus({'eos/access-base.j2'})
        for devtype in devtypes:
            self.assertEqual(type(devtype[0]), DeviceType)
            self.assertEqual(type(devtype[1]), str)
        self.assertTrue((DeviceType.ACCESS, 'eos') in devtypes)

    def test_savecommit(self):
        self.assertFalse(
            repo_chekout_working(RepoType.SETTINGS, dry_run=True),
            "Redis working commit not cleared at setUp")
        self.assertFalse(
            repo_chekout_working(RepoType.TEMPLATES, dry_run=True),
            "Redis working commit not cleared at setUp")
        repo_save_working_commit(RepoType.SETTINGS, "bd5e1f70f52037e8e2a451b2968a9ca8160a7cba")
        repo_save_working_commit(RepoType.TEMPLATES, "bd5e1f70f52037e8e2a451b2968a9ca8160a7cba")
        self.assertTrue(
            repo_chekout_working(RepoType.SETTINGS, dry_run=True),
            "Working commit not saved in redis")
        self.assertTrue(
            repo_chekout_working(RepoType.TEMPLATES, dry_run=True),
            "Working commit not saved in redis")


if __name__ == '__main__':
    unittest.main()
