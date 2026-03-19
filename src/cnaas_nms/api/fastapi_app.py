from authlib.oauth2.rfc6749 import MissingAuthorizationError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from flask_jwt_extended.exceptions import InvalidHeaderError, NoAuthorizationError
from jwt.exceptions import DecodeError, ExpiredSignatureError, InvalidKeyError, InvalidSignatureError, InvalidTokenError

from cnaas_nms.api.response import CnaasJSONResponse
from cnaas_nms.api.routers import groups, jobs, linknet, mgmtdomain, plugins, repository, settings, system
from cnaas_nms.tools.log import get_logger
from cnaas_nms.version import __api_version__

logger = get_logger()


app = FastAPI(
    title="CNaaS NMS API",
    version=__api_version__,
    docs_url="/api/doc/",
    openapi_url="/api/openapi.json",
    default_response_class=CnaasJSONResponse,
)

# CORS — same config as Flask app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Authorization", "X-Total-Count", "Link", "Set-Cookie", "Cookie"],
)


# --- Exception handlers matching CnaasApi.handle_error() in api/app.py ---


@app.exception_handler(DecodeError)
async def decode_error_handler(request: Request, exc: DecodeError) -> CnaasJSONResponse:
    return CnaasJSONResponse(status_code=401, content={"status": "error", "message": "Could not decode JWT token"})


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError) -> CnaasJSONResponse:
    return CnaasJSONResponse(
        status_code=403,
        content={"status": "error", "message": "You don't seem to have the rights to execute this call"},
    )


@app.exception_handler(ExpiredSignatureError)
async def expired_sig_handler(request: Request, exc: ExpiredSignatureError) -> CnaasJSONResponse:
    return CnaasJSONResponse(
        status_code=401,
        content={"status": "error", "message": "The JWT token is expired", "errorCode": "auth_expired"},
    )


@app.exception_handler(InvalidKeyError)
async def invalid_key_handler(request: Request, exc: InvalidKeyError) -> CnaasJSONResponse:
    return CnaasJSONResponse(status_code=401, content={"status": "error", "data": "Invalid keys {}".format(exc)})


@app.exception_handler(InvalidTokenError)
async def invalid_token_handler(request: Request, exc: InvalidTokenError) -> CnaasJSONResponse:
    return CnaasJSONResponse(
        status_code=401,
        content={"status": "error", "message": "Invalid authentication header: {}".format(exc)},
    )


@app.exception_handler(InvalidSignatureError)
async def invalid_sig_handler(request: Request, exc: InvalidSignatureError) -> CnaasJSONResponse:
    return CnaasJSONResponse(status_code=401, content={"status": "error", "message": "Invalid token signature"})


@app.exception_handler(InvalidHeaderError)
async def invalid_header_handler(request: Request, exc: InvalidHeaderError) -> CnaasJSONResponse:
    return CnaasJSONResponse(
        status_code=401,
        content={"status": "error", "message": "Invalid header, JWT token missing? {}".format(exc)},
    )


@app.exception_handler(MissingAuthorizationError)
async def missing_auth_handler(request: Request, exc: MissingAuthorizationError) -> CnaasJSONResponse:
    return CnaasJSONResponse(status_code=401, content={"status": "error", "message": "JWT token missing?"})


@app.exception_handler(NoAuthorizationError)
async def no_auth_handler(request: Request, exc: NoAuthorizationError) -> CnaasJSONResponse:
    return CnaasJSONResponse(status_code=401, content={"status": "error", "message": "JWT token missing?"})


@app.exception_handler(ConnectionError)
async def connection_error_handler(request: Request, exc: ConnectionError) -> CnaasJSONResponse:
    return CnaasJSONResponse(
        status_code=500,
        content={"status": "error", "message": "ConnectionError: {}".format(exc)},
    )


# --- Request logging middleware ---


@app.middleware("http")
async def log_request_middleware(request: Request, call_next):  # type: ignore
    response = await call_next(request)

    user = "unknown"
    if "/auth/" not in str(request.url):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from cnaas_nms.app_settings import auth_settings

                if auth_settings.OIDC_ENABLED:
                    from cnaas_nms.tools.oidc.oidc_client_call import get_oauth_token_info
                    from cnaas_nms.tools.security import MyBearerTokenValidator

                    token_string = auth_header.split(" ")[-1]
                    validator = MyBearerTokenValidator()
                    token = validator.authenticate_token(token_string)
                    token_info = get_oauth_token_info(token)
                    if token_info and auth_settings.OIDC_USERNAME_ATTRIBUTE in token_info:
                        user = token_info[auth_settings.OIDC_USERNAME_ATTRIBUTE]
                    elif token_info and "client_id" in token_info:
                        user = token_info["client_id"]
                else:
                    from flask_jwt_extended import decode_token

                    token_string = auth_header.split(" ")[-1]
                    user = decode_token(token_string).get("sub", "unknown")
            except Exception:
                user = "unknown"
    else:
        user = "unauthenticated"

    logger.info(
        "User: {}, Method: {}, Status: {}, URL: {}".format(user, request.method, response.status_code, request.url)
    )
    return response


# --- Register routers ---

api_prefix = "/api/{}".format(__api_version__)
app.include_router(system.router, prefix=api_prefix)
app.include_router(groups.router, prefix=api_prefix)
app.include_router(plugins.router, prefix=api_prefix)
app.include_router(repository.router, prefix=api_prefix)
app.include_router(settings.router, prefix=api_prefix)
app.include_router(jobs.router, prefix=api_prefix)
app.include_router(linknet.router, prefix=api_prefix)
app.include_router(mgmtdomain.router, prefix=api_prefix)
