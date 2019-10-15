import os


class TestAppWrapper(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        environ['HTTP_AUTHORIZATION'] = 'Bearer {}'.format(os.environ['JWT_AUTH_TOKEN'])
        return self.app(environ, start_response)
