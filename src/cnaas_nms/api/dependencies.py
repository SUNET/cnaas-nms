from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cnaas_nms.app_settings import api_settings, auth_settings
from cnaas_nms.tools.log import get_logger

logger = get_logger()

# Optional bearer — allows endpoints to work when JWT is disabled
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """FastAPI dependency that validates JWT/OIDC tokens and returns the username.

    Mirrors the behaviour of tools/security.py login_required + get_identity.
    """
    # If neither JWT nor OIDC is enabled, everyone is "admin"
    if not api_settings.JWT_ENABLED and not auth_settings.OIDC_ENABLED:
        return "admin"

    if credentials is None:
        raise HTTPException(status_code=401, detail="JWT token missing")

    token_string = credentials.credentials

    if auth_settings.OIDC_ENABLED:
        from cnaas_nms.tools.oidc.oidc_client_call import get_oauth_token_info
        from cnaas_nms.tools.security import MyBearerTokenValidator

        validator = MyBearerTokenValidator()
        token = validator.authenticate_token(token_string)
        token_info = get_oauth_token_info(token)
        if auth_settings.OIDC_USERNAME_ATTRIBUTE in token_info:
            return token_info[auth_settings.OIDC_USERNAME_ATTRIBUTE]
        elif "client_id" in token_info:
            return token_info["client_id"]
        else:
            raise HTTPException(status_code=401, detail="Could not determine user identity from token")
    else:
        # JWT mode — decode with ES256 public key
        from flask_jwt_extended import decode_token

        try:
            decoded = decode_token(token_string)
            return decoded.get("sub", "unknown")
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Invalid JWT token: {e}")


@dataclass
class PaginationParams:
    """Query parameters for paginated endpoints."""

    page: int = 1
    per_page: int = 50

    def __post_init__(self) -> None:
        if not 1 <= self.per_page <= 1000:
            raise HTTPException(status_code=400, detail="per_page must be between 1 and 1000")
        self.page = max(1, self.page)

    @property
    def limit(self) -> int:
        return self.per_page

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page
