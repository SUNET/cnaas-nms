def setup_package():
    import cnaas_nms.api.app
    from cnaas_nms.api.tests.app_wrapper import TestAppWrapper

    app = cnaas_nms.api.app.app
    app.wsgi_app = TestAppWrapper(app.wsgi_app, None)  # type: ignore
    client = app.test_client()
    data = {"action": "refresh"}
    client.put("/api/v1.0/repository/settings", json=data)
    client.put("/api/v1.0/repository/templates", json=data)
