import os
import unittest

from cnaas_nms.tools.jinja_helpers import get_environment_secrets


class EnvironmentSecretsTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["TEMPLATE_SECRET_FOO"] = "bar"  # noqa: S105
        os.environ["TEMPLATE_SECRET_TEST_TYPE"] = "cromulent"  # noqa: S105
        os.environ["NOT_A_SECRET"] = "foobar"  # noqa: S105

    def tearDown(self) -> None:
        del os.environ["TEMPLATE_SECRET_FOO"]
        del os.environ["TEMPLATE_SECRET_TEST_TYPE"]
        del os.environ["NOT_A_SECRET"]

    def test_that_individual_secrets_are_present(self):
        secrets = get_environment_secrets()
        self.assertEquals(secrets["TEMPLATE_SECRET_FOO"], "bar")
        self.assertEquals(secrets["TEMPLATE_SECRET_TEST_TYPE"], "cromulent")

    def test_that_secret_dict_is_set_properly(self):
        secrets = get_environment_secrets()
        self.assertIn("TEMPLATE_SECRET", secrets)

        secret_dict = secrets.get("TEMPLATE_SECRET")
        self.assertEquals(secret_dict["FOO"], "bar")
        self.assertEquals(secret_dict["TEST_TYPE"], "cromulent")

    def test_that_non_secret_variables_arent_included(self):
        secrets = get_environment_secrets()
        self.assertNotIn("NOT_A_SECRET", secrets)
