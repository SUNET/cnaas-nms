__import__('pkg_resources').declare_namespace(__name__)


def setup_package():
    import cnaas_nms.api.app
    client = cnaas_nms.api.app.app.test_client()
    data = {"action": "refresh"}
    client.put('/api/v1.0/repository/settings', json=data)
    client.put('/api/v1.0/repository/templates', json=data)
