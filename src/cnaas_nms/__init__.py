import sys

"""
Patches TypedDict so it is loaded from typing_extensions for python version < 3.12, eq 3.11
Aerleon imports typing.TypedDict which is not supported with Pydantic.

Error:
pydantic.errors.PydanticUserError: Please use `typing_extensions.TypedDict` instead of `typing.TypedDict` on Python < 3.12.

This can be removed when updating a version >= 3.12
"""

if sys.version_info < (3, 12):
    import typing  # noqa: I001
    from typing_extensions import TypedDict

    typing.TypedDict = TypedDict  # override


__import__("pkg_resources").declare_namespace(__name__)


def setup_package():
    import cnaas_nms.api.app
    from cnaas_nms.api.tests.app_wrapper import TestAppWrapper

    app = cnaas_nms.api.app.app
    app.wsgi_app = TestAppWrapper(app.wsgi_app, None)  # type: ignore
    client = app.test_client()
    data = {"action": "refresh"}
    client.put("/api/v1.0/repository/settings", json=data)
    client.put("/api/v1.0/repository/templates", json=data)
