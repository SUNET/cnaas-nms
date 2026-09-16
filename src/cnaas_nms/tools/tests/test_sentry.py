import unittest
from typing import Any
from unittest.mock import mock_open, patch

import sentry_sdk
from sentry_sdk.transport import Transport

from cnaas_nms.app_settings import SentrySettings, construct_sentry_settings
from cnaas_nms.tools.sentry import sentry_init

TEST_DSN = "https://publickey@sentry.example.com/1"
OTHER_DSN = "https://publickey@sentry.example.com/2"

SECRET = "secret-token"


class CapturingTransport(Transport):
    """Stands in for Sentry's HTTP transport and keeps every event that would be sent."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, Any]] = []

    def capture_envelope(self, envelope) -> None:
        for item in envelope.items:
            event = item.get_event() or item.get_transaction_event()
            if event is not None:
                self.events.append(event)


class SentryTestCase(unittest.TestCase):
    def tearDown(self):
        # Detach the client so one test can't leak an active Sentry into the next
        sentry_sdk.get_global_scope().set_client(None)

    def enable_sentry(self, component: str = "api", **settings: Any) -> CapturingTransport:
        """Initialise Sentry as a running process does, but capture events instead of sending them."""
        with patch("cnaas_nms.tools.sentry.sentry_settings", SentrySettings(SENTRY_DSN=TEST_DSN, **settings)):
            sentry_init(component)
        transport = CapturingTransport()
        sentry_sdk.get_client().transport = transport
        return transport

    def report_error(self, **scope: Any) -> dict[str, Any]:
        """Report a failure the way an unhandled error in the API does, and return the event that would be sent."""
        with sentry_sdk.new_scope() as current:
            for key, value in scope.items():
                current.set_extra(key, value)
            try:
                raise ValueError("device sync failed")
            except ValueError:
                sentry_sdk.capture_exception()
        sentry_sdk.flush()
        return self.only_event(sentry_sdk.get_client().transport)

    def only_event(self, transport: CapturingTransport) -> dict[str, Any]:
        self.assertEqual(len(transport.events), 1, "expected exactly one event to be sent")
        return transport.events[0]


class SentryConfigTests(unittest.TestCase):
    def construct_with_config(self, contents: str) -> SentrySettings:
        with (
            patch("cnaas_nms.app_settings.Path.is_file", return_value=True),
            patch("builtins.open", mock_open(read_data=contents)),
        ):
            return construct_sentry_settings()

    def test_environment_enables_sentry_when_the_packaged_file_leaves_the_dsn_empty(self):
        """The container always ships sentry_config.yml with an empty dsn, so SENTRY_DSN must still take effect."""
        with patch.dict("os.environ", {"SENTRY_DSN": TEST_DSN}):
            settings = self.construct_with_config('dsn: ""\n')

        self.assertEqual(settings.SENTRY_DSN, TEST_DSN)

    def test_configured_file_wins_over_the_environment(self):
        with patch.dict("os.environ", {"SENTRY_DSN": OTHER_DSN}):
            settings = self.construct_with_config("dsn: {}\n".format(TEST_DSN))

        self.assertEqual(settings.SENTRY_DSN, TEST_DSN)

    def test_every_documented_setting_can_be_configured_from_the_environment(self):
        """The Compose file forwards each of these, so each has to reach the settings."""
        environment = {
            "SENTRY_DSN": TEST_DSN,
            "SENTRY_ENVIRONMENT": "production",
            "SENTRY_RELEASE": "cnaas-nms@custom",
            "SENTRY_TRACES_SAMPLE_RATE": "0.5",
            "SENTRY_SAMPLE_RATE": "0.25",
            "SENTRY_SEND_DEFAULT_PII": "True",
        }
        with patch.dict("os.environ", environment):
            settings = self.construct_with_config('dsn: ""\n')

        self.assertEqual(settings.SENTRY_ENVIRONMENT, "production")
        self.assertEqual(settings.SENTRY_RELEASE, "cnaas-nms@custom")
        self.assertEqual(settings.SENTRY_TRACES_SAMPLE_RATE, 0.5)
        self.assertEqual(settings.SENTRY_SAMPLE_RATE, 0.25)
        self.assertTrue(settings.SENTRY_SEND_DEFAULT_PII)

    def test_invalid_sample_rate_is_rejected(self):
        with self.assertRaises(ValueError):
            SentrySettings(SENTRY_SAMPLE_RATE=1.5)


class SentryReportingTests(SentryTestCase):
    def test_nothing_is_reported_without_a_dsn(self):
        """Deployments that don't configure Sentry must not report anything."""
        with patch("cnaas_nms.tools.sentry.sentry_settings", SentrySettings(SENTRY_DSN=None)):
            enabled = sentry_init("api")

        self.assertFalse(enabled)
        self.assertFalse(sentry_sdk.get_client().is_active())

    def test_an_error_is_reported_when_a_dsn_is_configured(self):
        transport = self.enable_sentry()

        event = self.report_error()

        self.assertIn("device sync failed", str(event))
        self.assertEqual(len(transport.events), 1)

    def test_the_reporting_component_is_named_so_api_and_scheduler_can_be_told_apart(self):
        self.enable_sentry(component="scheduler_mule")

        event = self.report_error()

        self.assertEqual(event["tags"]["component"], "scheduler_mule")

    def test_an_error_is_reported_against_the_running_version(self):
        from cnaas_nms.version import __version__

        self.enable_sentry()

        event = self.report_error()

        self.assertEqual(event["release"], "cnaas-nms@{}".format(__version__))

    def test_a_configured_release_is_reported_instead_of_the_version(self):
        self.enable_sentry(SENTRY_RELEASE="cnaas-nms@custom")

        event = self.report_error()

        self.assertEqual(event["release"], "cnaas-nms@custom")

    def test_personal_data_is_not_reported_by_default(self):
        """Events must not identify the user who happened to trigger an error."""
        self.enable_sentry()

        event = self.report_error()

        self.assertIsNone(event.get("user"))


class CredentialScrubbingTests(SentryTestCase):
    """No credential may leave the process, whichever part of an event carries it."""

    def report_with_secret_in(self, **scope: Any) -> str:
        self.enable_sentry()
        return str(self.report_error(**scope))

    def assert_scrubbed(self, reported: str, kept: str | None = None) -> None:
        self.assertNotIn(SECRET, reported)
        if kept is not None:
            self.assertIn(kept, reported, "scrubbing must keep the data that makes an error diagnosable")

    def test_a_bearer_token_held_while_authenticating_is_not_reported(self):
        """The API binds a bearer JWT to a local named token_string while it authenticates a request."""
        self.enable_sentry()

        with sentry_sdk.new_scope():
            try:
                token_string = SECRET  # noqa: F841 - captured as a stack frame local
                raise ValueError("device sync failed")
            except ValueError:
                sentry_sdk.capture_exception()
        sentry_sdk.flush()

        self.assert_scrubbed(str(self.only_event(sentry_sdk.get_client().transport)), kept="device sync failed")

    def test_a_token_in_a_request_url_is_not_reported(self):
        """A Flask request renders as its full URL, so a token in the query string reaches an event."""
        reported = self.report_with_secret_in(
            request="<Request 'http://localhost/api/v1.0/devices?jwt={}' [GET]>".format(SECRET)
        )

        self.assert_scrubbed(reported, kept="/api/v1.0/devices")

    def test_an_oidc_authorization_code_is_not_reported(self):
        reported = self.report_with_secret_in(
            redirect="http://localhost/auth/callback?code={}&state=xyz".format(SECRET)
        )

        self.assert_scrubbed(reported, kept="state=xyz")

    def test_an_oidc_access_token_in_a_redirect_is_not_reported(self):
        """The OIDC login redirect carries the access token to the frontend."""
        reported = self.report_with_secret_in(
            message="redirecting to http://localhost/callback?token={}&username=admin".format(SECRET)
        )

        self.assert_scrubbed(reported, kept="username=admin")

    def test_a_credential_in_a_named_field_is_not_reported(self):
        """Tokens reach an event as the value of a named field, not only inside a URL."""
        reported = self.report_with_secret_in(
            token={"access_token": SECRET, "refresh_token": SECRET}, hostname="eosdist1"
        )

        self.assert_scrubbed(reported, kept="eosdist1")

    def test_a_credential_in_a_logged_request_body_is_not_reported(self):
        """The API logs a request body into its message, so a credential arrives as serialized text."""
        reported = self.report_with_secret_in(
            message="Method: POST, URL: /api/v1.0/device_syncto, "
            "JSON: {{'hostname': 'eosdist1', 'fencing_token': '{}'}}".format(SECRET)
        )

        self.assert_scrubbed(reported, kept="'hostname': 'eosdist1'")

    def test_a_token_in_a_transaction_is_not_reported(self):
        """Performance monitoring sends transactions, which carry the request URL and its query string."""
        transport = self.enable_sentry(SENTRY_TRACES_SAMPLE_RATE=1.0)

        with sentry_sdk.start_transaction(name="/api/v1.0/devices?jwt={}".format(SECRET), op="http.server"):
            pass
        sentry_sdk.flush()

        self.assert_scrubbed(str(self.only_event(transport)), kept="/api/v1.0/devices")

    def test_device_data_that_merely_looks_like_a_credential_is_reported(self):
        """Scrubbing must not blank out the device data that makes an error diagnosable."""
        self.enable_sentry()

        event = self.report_error(barcode="12345", device_code="xyz", url="/api/v1.0/devices?hostname=jwtdist1")

        self.assertEqual(event["extra"]["barcode"], "12345")
        self.assertEqual(event["extra"]["device_code"], "xyz")
        self.assertEqual(event["extra"]["url"], "/api/v1.0/devices?hostname=jwtdist1")

    def test_an_error_without_a_request_is_reported(self):
        """Scheduler jobs fail with no HTTP request attached, and those errors still have to arrive."""
        self.enable_sentry(component="scheduler_mule")

        event = self.report_error(hostname="eosdist1")

        self.assertIn("device sync failed", str(event))
        self.assertEqual(event["extra"]["hostname"], "eosdist1")
