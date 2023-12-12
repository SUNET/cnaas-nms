
class Token():
    token_string: str = ""
    decoded_token = {}
    expires_at = ""

    def __init__(self, token_string: str, decoded_token: dict):
        self.token_string = token_string
        self.decoded_token = decoded_token