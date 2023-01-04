import os


class TestAppWrapper(object):
    __test__ = False

    def __init__(self, app, jwt_auth_token):
        self.app = app
        self.jwt_auth_token = jwt_auth_token

    def __call__(self, environ, start_response):
        if 'JWT_AUTH_TOKEN' in os.environ:
            environ['HTTP_AUTHORIZATION'] = 'Bearer {}'.format(os.environ['JWT_AUTH_TOKEN'])
        elif self.jwt_auth_token:
            environ['HTTP_AUTHORIZATION'] = 'Bearer {}'.format(self.jwt_auth_token)
        return self.app(environ, start_response)
