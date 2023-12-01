
class Token():
    token_string: str = ""
    decoded_token = {}
    token_type: str = ""
    audience: str = ""
    expires_at = ""

    def __init__(self, token_string: str, decoded_token: dict, algorithm: str):
        self.token_string = token_string
        self.decoded_token = decoded_token
        self.token_type = algorithm
        self.expires_at = decoded_token["exp"]