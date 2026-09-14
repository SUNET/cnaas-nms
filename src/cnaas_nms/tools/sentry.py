"""Optional Sentry error reporting.

Sentry is only enabled when a DSN is configured, so deployments that do not use
Sentry run without the SDK doing any work.
"""

import re
from typing import TYPE_CHECKING, Any

from cnaas_nms.app_settings import sentry_settings
from cnaas_nms.version import __version__

if TYPE_CHECKING:
    from sentry_sdk._types import Event, Hint

# Names of fields holding a credential: anything ending in "jwt" or "token", plus
# the OIDC authorization code. Sentry knows "token" but only as an exact match,
# so "access_token" and friends reach an event untouched.
SENSITIVE_NAME = r"[\w-]*(?:jwt|token)|code"

SENSITIVE_NAME_RE = re.compile(SENSITIVE_NAME, re.IGNORECASE)

_FILTERED = "[Filtered]"

# The same credentials passed as a query parameter. Sentry scrubs credentials
# from headers and request bodies by name, but leaves the query string untouched,
# and a URL repeated inside a log message or a stack frame local (a Flask request
# renders as its full URL, and the OIDC login redirect carries the access token)
# never passes through that scrubbing at all.
SENSITIVE_QUERY_RE = re.compile(r"\b(?P<param>{})=[^&\s\"'>]+".format(SENSITIVE_NAME), re.IGNORECASE)


def _is_sensitive_name(name: Any) -> bool:
    """Report whether a field name holds a credential."""
    return isinstance(name, str) and SENSITIVE_NAME_RE.fullmatch(name) is not None


def _redact(value: str) -> str:
    """Replace credential query parameter values in a string."""
    return SENSITIVE_QUERY_RE.sub(lambda match: "{}={}".format(match.group("param"), _FILTERED), value)


def _scrub_event(event: "Event", hint: "Hint") -> "Event":
    """Remove credentials from every string in an event before it is sent."""

    def walk(node: Any) -> Any:
        if isinstance(node, str):
            return _redact(node)
        if isinstance(node, dict):
            return {key: _FILTERED if _is_sensitive_name(key) else walk(value) for key, value in node.items()}
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, tuple):
            return tuple(walk(item) for item in node)
        return node

    return walk(event)


def sentry_init(component: str) -> bool:
    """Initialise Sentry error reporting for a CNaaS NMS process.

    Args:
        component: Name of the process reporting errors, for example "api" or
            "scheduler_mule". Reported as the "component" tag so events from the
            API and the scheduler can be told apart.
    Returns:
        bool: True if Sentry was enabled, False if no DSN is configured.
    """
    if not sentry_settings.SENTRY_DSN:
        return False

    import sentry_sdk
    from sentry_sdk.scrubber import EventScrubber

    environment: str | None = sentry_settings.SENTRY_ENVIRONMENT
    release: str = sentry_settings.SENTRY_RELEASE or "cnaas-nms@{}".format(__version__)

    sentry_sdk.init(
        dsn=sentry_settings.SENTRY_DSN,
        environment=environment,
        release=release,
        traces_sample_rate=sentry_settings.SENTRY_TRACES_SAMPLE_RATE,
        sample_rate=sentry_settings.SENTRY_SAMPLE_RATE,
        send_default_pii=sentry_settings.SENTRY_SEND_DEFAULT_PII,
        event_scrubber=EventScrubber(recursive=True),
        before_send=_scrub_event,
    )
    sentry_sdk.get_global_scope().set_tag("component", component)
    return True
