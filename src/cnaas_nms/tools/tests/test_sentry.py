import unittest
from unittest.mock import mock_open, patch

import sentry_sdk

from cnaas_nms.app_settings import SentrySettings, construct_sentry_settings
from cnaas_nms.tools.sentry import _scrub_event, sentry_init

TEST_DSN = "https://publickey@sentry.example.com/1"


class SentryConfigTests(unittest.TestCase):
    def construct_with_config(self, contents: str) -> SentrySettings:
        with (
            patch("cnaas_nms.app_settings.Path.is_file", return_value=True),
            patch("builtins.open", mock_open(read_data=contents)),
        ):
            return construct_sentry_settings()

    def test_environment_enables_sentry_when_the_packaged_file_leaves_the_dsn_empty(self):
        """The container always ships sentry_config.yml, so SENTRY_DSN must still take effect."""
        with patch.dict("os.environ", {"SENTRY_DSN": TEST_DSN}):
            settings = self.construct_with_config('dsn: ""\n')

        self.assertEqual(settings.SENTRY_DSN, TEST_DSN)

    def test_configured_file_wins_over_the_environment(self):
        with patch.dict("os.environ", {"SENTRY_DSN": "https://publickey@sentry.example.com/2"}):
            settings = self.construct_with_config("dsn: {}\n".format(TEST_DSN))

        self.assertEqual(settings.SENTRY_DSN, TEST_DSN)


class SentryInitTests(unittest.TestCase):
    def tearDown(self):
        # Detach the client so one test can't leak an active Sentry into the next
        sentry_sdk.get_global_scope().set_client(None)

    def test_sentry_stays_disabled_without_dsn(self):
        """Deployments that don't configure Sentry must not report anything."""
        with patch("cnaas_nms.tools.sentry.sentry_settings", SentrySettings(SENTRY_DSN=None)):
            enabled = sentry_init("api")

        self.assertFalse(enabled)
        self.assertFalse(sentry_sdk.get_client().is_active())

    def test_sentry_is_enabled_with_dsn(self):
        with patch("cnaas_nms.tools.sentry.sentry_settings", SentrySettings(SENTRY_DSN=TEST_DSN)):
            enabled = sentry_init("api")

        self.assertTrue(enabled)
        self.assertTrue(sentry_sdk.get_client().is_active())

    def test_component_is_reported_to_tell_api_and_scheduler_apart(self):
        with patch("cnaas_nms.tools.sentry.sentry_settings", SentrySettings(SENTRY_DSN=TEST_DSN)):
            sentry_init("scheduler_mule")

        self.assertEqual(sentry_sdk.get_global_scope()._tags.get("component"), "scheduler_mule")

    def test_release_defaults_to_running_version(self):
        from cnaas_nms.version import __version__

        with patch("cnaas_nms.tools.sentry.sentry_settings", SentrySettings(SENTRY_DSN=TEST_DSN)):
            sentry_init("api")

        self.assertEqual(sentry_sdk.get_client().options["release"], "cnaas-nms@{}".format(__version__))

    def test_configured_release_overrides_version(self):
        with patch(
            "cnaas_nms.tools.sentry.sentry_settings",
            SentrySettings(SENTRY_DSN=TEST_DSN, SENTRY_RELEASE="cnaas-nms@custom"),
        ):
            sentry_init("api")

        self.assertEqual(sentry_sdk.get_client().options["release"], "cnaas-nms@custom")

    def test_transactions_are_scrubbed_like_errors(self):
        """Performance monitoring sends transactions, which carry the request URL and its query string."""
        with patch("cnaas_nms.tools.sentry.sentry_settings", SentrySettings(SENTRY_DSN=TEST_DSN)):
            sentry_init("api")

        self.assertEqual(sentry_sdk.get_client().options["before_send_transaction"], _scrub_event)

    def test_personal_data_is_not_sent_by_default(self):
        with patch("cnaas_nms.tools.sentry.sentry_settings", SentrySettings(SENTRY_DSN=TEST_DSN)):
            sentry_init("api")

        self.assertFalse(sentry_sdk.get_client().options["send_default_pii"])

    def test_invalid_sample_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            SentrySettings(SENTRY_SAMPLE_RATE=1.5)


class ScrubEventTests(unittest.TestCase):
    def test_jwt_token_is_not_reported(self):
        """A token in the query string grants API access, so it must never reach Sentry."""
        event = _scrub_event({"request": {"query_string": "jwt=secret-token&hostname=eosdist1"}}, {})

        self.assertNotIn("secret-token", event["request"]["query_string"])
        self.assertIn("hostname=eosdist1", event["request"]["query_string"])

    def test_oidc_authorization_code_is_not_reported(self):
        event = _scrub_event({"request": {"query_string": "code=secret-code&state=xyz"}}, {})

        self.assertNotIn("secret-code", event["request"]["query_string"])
        self.assertIn("state=xyz", event["request"]["query_string"])

    def test_token_in_a_stacktrace_local_is_not_reported(self):
        """A Flask request renders as its full URL, so tokens reach stack frame locals."""
        event = {
            "exception": {
                "values": [
                    {
                        "stacktrace": {
                            "frames": [
                                {
                                    "vars": {
                                        "req": "<Request 'http://localhost/api/v1.0/devices?jwt=secret-token' [GET]>"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        }

        scrubbed = _scrub_event(event, {})

        self.assertNotIn("secret-token", str(scrubbed))

    def test_oidc_access_token_in_a_redirect_url_is_not_reported(self):
        """The OIDC login redirect carries the access token to the frontend."""
        event = {"logentry": {"message": "redirecting to http://localhost/callback?token=secret-token&username=a"}}

        scrubbed = _scrub_event(event, {})

        self.assertNotIn("secret-token", str(scrubbed))
        self.assertIn("username=a", scrubbed["logentry"]["message"])

    def test_credentials_held_in_a_named_field_are_not_reported(self):
        """Tokens reach an event as values of a named field, not only inside URLs."""
        event = {
            "extra": {
                "token": {"access_token": "secret-access", "refresh_token": "secret-refresh"},
                "hostname": "eosdist1",
            }
        }

        scrubbed = _scrub_event(event, {})

        self.assertNotIn("secret-access", str(scrubbed))
        self.assertNotIn("secret-refresh", str(scrubbed))
        self.assertEqual(scrubbed["extra"]["hostname"], "eosdist1")

    def test_data_that_merely_looks_like_a_credential_is_kept(self):
        """Scrubbing must not blank out the device data that makes an error diagnosable."""
        event = {"extra": {"barcode": "12345", "device_code": "xyz", "url": "/api/v1.0/devices?hostname=jwtdist1"}}

        scrubbed = _scrub_event(event, {})

        self.assertEqual(scrubbed["extra"], event["extra"])

    def test_bearer_token_in_a_stacktrace_local_is_not_reported(self):
        """The API holds a bearer JWT in a local named token_string while it authenticates a request."""
        event = {"exception": {"values": [{"stacktrace": {"frames": [{"vars": {"token_string": "secret-token"}}]}}]}}

        scrubbed = _scrub_event(event, {})

        self.assertNotIn("secret-token", str(scrubbed))

    def test_credential_in_a_logged_request_body_is_not_reported(self):
        """The API logs a request body into its message, so a credential arrives as serialized text."""
        event = {
            "logentry": {
                "message": "Method: POST, URL: /api/v1.0/device_syncto, "
                "JSON: {'hostname': 'eosdist1', 'fencing_token': 'secret-token'}"
            }
        }

        scrubbed = _scrub_event(event, {})

        self.assertNotIn("secret-token", str(scrubbed))
        self.assertIn("'hostname': 'eosdist1'", scrubbed["logentry"]["message"])

    def test_token_in_a_log_message_is_not_reported(self):
        event = {"logentry": {"message": "request failed for /api/v1.0/devices?jwt=secret-token"}}

        scrubbed = _scrub_event(event, {})

        self.assertNotIn("secret-token", str(scrubbed))

    def test_events_without_a_request_are_passed_through(self):
        """Background job errors have no HTTP request attached."""
        event = _scrub_event({"exception": {"values": []}}, {})

        self.assertEqual(event, {"exception": {"values": []}})
