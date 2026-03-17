# FastAPI Migration Plan for CNaaS-NMS

## Context

CNaaS-NMS currently uses Flask 3.1.3 + Flask-RESTX 1.3 for its REST API, with Flask-SocketIO for WebSockets, Flask-JWT-Extended for JWT auth, and gevent/uWSGI for production. The goal is to migrate to FastAPI while:
- Keeping the API 100% backwards compatible (same URLs, response format, auth)
- Using Pydantic 2.10+ for request/response validation (already on 2.11.3)
- Adding unit tests before refactoring areas with low coverage

The codebase already uses Pydantic for validation in several places (settings_fields, stackmembers, linknet, mgmtdomain, permissions, app_settings). Flask-RESTX `fields` models are only used for Swagger docs, not validation — actual validation is mostly inline.

## Key Choices

- **First pass**: PR 1 (foundation) + PR 2 (simple endpoints) combined
- **ASGI server**: gunicorn + uvicorn workers for production
- **Transition**: Dual-stack — Flask stays running, FastAPI built in `api/routers/`, final PR switches over

## Migration Strategy: Incremental, PR-by-PR

Each PR is independently deployable. New FastAPI routers coexist with Flask until the final switchover.

---

### PR 1: Foundation + Simple Endpoints + Test Safety Net ✅

**Goal**: FastAPI app skeleton, shared infrastructure, unit tests for untested utilities, AND the 3 simplest endpoints (system, groups, plugins).

#### New files:
- `src/cnaas_nms/api/fastapi_app.py` — FastAPI app factory with:
  - CORS middleware (same config as Flask: `origins="*"`, exposed headers `X-Total-Count`, `Link`, etc.)
  - Exception handlers matching `CnaasApi.handle_error()` in `api/app.py:59-96`
  - Custom JSON response class handling IP address serialization (replacing `api/json.py` CNaaSJSONEncoder)
  - Request logging middleware (replacing `app.py:222-263` `@app.after_request`)
  - OpenAPI docs at `/api/doc/`

- `src/cnaas_nms/api/dependencies.py` — FastAPI dependencies:
  - `get_current_user` — unified JWT/OIDC auth dependency (replaces `tools/security.py` `login_required` decorator). Reuses `MyBearerTokenValidator` which is framework-agnostic.
  - `PaginationParams` — dataclass with `page: int = 1, per_page: int = 50`

- `src/cnaas_nms/api/response.py` — Standard response helpers:
  - `empty_result()` — same signature as `generic.py:167-173`, framework-agnostic
  - `CnaasJSONResponse` — JSONResponse subclass with IP serialization

- `src/cnaas_nms/api/filtering.py` — Framework-agnostic versions of:
  - `build_filter(f_class, query, args, per_page, page)` — same as `generic.py:102-164` but takes explicit params instead of `flask.request`
  - `pagination_headers(total_count, args, per_page, page, base_url)` — same as `generic.py:59-99`

- `src/cnaas_nms/api/tests/fastapi_client.py` — TestClient wrapper with JWT injection (equivalent to `api/tests/app_wrapper.py`)

#### New test files:
- `src/cnaas_nms/api/tests/test_generic.py` — Unit tests for `empty_result`, `build_filter`, `pagination_headers`, `parse_pydantic_error`, `update_sqla_object`
- `src/cnaas_nms/api/tests/test_fastapi_foundation.py` — Tests for CORS, error handlers, auth dependency

#### Modified files:
- `pyproject.toml` — Add: `fastapi`, `uvicorn[standard]`, `python-socketio[asyncio]`, `httpx` (for TestClient). Keep Flask deps during transition.

#### Key decisions:
- Endpoints remain `def` (sync, not `async def`) — SQLAlchemy sessions are synchronous, FastAPI runs sync handlers in thread pool automatically
- `generic.py` functions that depend on `flask.request` get parallel framework-agnostic versions in `filtering.py`; old ones stay until Flask is removed

---

#### Simple endpoint files (included in PR 1):
- `src/cnaas_nms/api/routers/system.py` — 2 endpoints: `GET /system/version`, `POST /system/shutdown`
- `src/cnaas_nms/api/routers/groups.py` — 3 endpoints: `GET /groups`, `GET /groups/{group_name}`, `GET /groups/{group_name}/os_version`
- `src/cnaas_nms/api/routers/plugins.py` — 2 endpoints: `GET /plugins`, `PUT /plugins`
- `src/cnaas_nms/api/models/common_models.py` — `PluginAction(action: str)`, `RepositoryAction(action: str)`

#### Pattern (Flask-RESTX Resource → FastAPI router):
```python
# Before (Flask-RESTX)
class DevicesApi(Resource):
    @login_required
    def get(self):
        return empty_result(...)
api.add_resource(DevicesApi, "/devices")

# After (FastAPI)
router = APIRouter(tags=["devices"])
@router.get("/devices")
def get_devices(user: str = Depends(get_current_user)):
    return empty_result(...)
```

---

### PR 2: Repository, Settings, Jobs ✅

#### New files:
- `src/cnaas_nms/api/routers/repository.py` — `GET/PUT /repository/{repo}`
- `src/cnaas_nms/api/routers/settings.py` — `GET /settings`, `GET /settings/model`, `POST /settings/model`
- `src/cnaas_nms/api/routers/jobs.py` — `GET /jobs`, `GET/PUT /job/{job_id}`, `GET/DELETE /joblocks`
- `src/cnaas_nms/api/models/job_models.py` — `JobAction(action: str, abort_reason: Optional[str])`

#### Key: Jobs endpoints use `build_filter` + pagination with `X-Total-Count`/`Link` headers — uses the new `filtering.py` functions with `Response` parameter injection.

---

### PR 3: Linknet + Management Domain

Already use Pydantic (`f_linknet`, `f_mgmtdomain`) — cleanest conversions.

#### New files:
- `src/cnaas_nms/api/routers/linknet.py` — CRUD for `/linknets`, `/linknet/{id}`
- `src/cnaas_nms/api/routers/mgmtdomain.py` — CRUD for `/mgmtdomains`, `/mgmtdomain/{id}`
- Pydantic models reuse existing `f_linknet`, `f_mgmtdomain` from their respective files

---

### PR 4: Interface + Firmware

#### New files:
- `src/cnaas_nms/api/routers/interface.py` — `GET/PUT /device/{hostname}/interfaces`
- `src/cnaas_nms/api/routers/firmware.py` — firmware endpoints
- `src/cnaas_nms/api/models/interface_models.py` — Replace 200 lines of manual type-checking in `interface.py:100-300` with Pydantic models
- `src/cnaas_nms/api/models/firmware_models.py`

---

### PR 5-6: Device Endpoints (split in two)

**PR 5 — Read-only**: `GET /device/{id}`, `GET /devices`, `GET /device/{hostname}/generate_config`, running_config, previous_config, LLDP neighbors, sync history

**PR 6 — Write**: `POST /devices`, `PUT /device/{id}`, `DELETE /device/{id}`, device_init, device_syncto, device_discover, device_update_facts, device_update_interfaces, device_cert, apply_config, stackmembers

#### New files:
- `src/cnaas_nms/api/routers/device.py` (or split into `device_read.py` / `device_write.py`)
- `src/cnaas_nms/api/models/device_models.py` — Pydantic models replacing Flask-RESTX field definitions at `device.py:82-238`

---

### PR 7: Auth/OIDC Endpoints

Most complex due to deep Flask integration. Switch from `authlib.integrations.flask_client` to `authlib.integrations.starlette_client`.

#### New files:
- `src/cnaas_nms/api/routers/auth.py`

#### Modified:
- `tools/security.py` — Add FastAPI-compatible auth functions alongside Flask ones (both coexist during transition)

---

### PR 8: WebSocket Migration

Replace Flask-SocketIO with `python-socketio` ASGI mode.

#### New files:
- `src/cnaas_nms/api/socketio_app.py` — `AsyncServer` with same connect/events handlers

#### Modified:
- `run.py` — Mount SocketIO ASGI app onto FastAPI app
- Redis polling thread stays same but calls new `sio.emit()`

---

### PR 9: Final Switchover + Cleanup

#### Modified:
- `run.py` — Replace gevent/Flask-SocketIO startup with gunicorn+uvicorn
- `pyproject.toml` — Remove flask, flask-restx, flask-socketio, flask-jwt-extended, flask-cors, gevent, greenlet
- Docker configs — Switch from uWSGI to gunicorn with uvicorn workers

#### Deleted:
- Old Flask `api/app.py`, old Flask route files (after verifying all tests pass against FastAPI)

---

## Backwards Compatibility Checklist (every PR)

- [ ] Same URL paths (`/api/v1.0/...`)
- [ ] Same response envelope: `{"status": "success/error", "data/message": ...}`
- [ ] Same HTTP status codes for same conditions
- [ ] Same query params: `filter[field][op]`, `per_page`, `page`, `sort`
- [ ] Same response headers: `X-Total-Count`, `Link`
- [ ] Same auth: `Authorization: Bearer <jwt>` header
- [ ] Same WebSocket protocol: `connect` with `?jwt=`, `events` with room data
- [ ] IP addresses serialize to strings

## Key Architectural Decisions

1. **Sync endpoints, not async** — SQLAlchemy sessions are sync; FastAPI runs `def` handlers in thread pool. No need to convert to async SQLAlchemy.
2. **No gevent** — FastAPI uses uvicorn (asyncio). Remove gevent monkey patching at final switchover.
3. **`sqla_session()` unchanged** — Context manager pattern works fine from sync FastAPI handlers.
4. **Coexistence during transition** — Both Flask and FastAPI apps can exist; tests run against FastAPI from PR 1 onwards.

## Critical Files

| File | Role | Action |
|------|------|--------|
| `api/app.py` (264 lines) | Flask app setup, error handling, CORS, JWT, SocketIO, namespaces, logging | Replicate in `fastapi_app.py`, delete at end |
| `api/generic.py` (213 lines) | `empty_result`, `build_filter`, pagination — used by every endpoint | Create framework-agnostic versions in `filtering.py` + `response.py` |
| `tools/security.py` (150 lines) | `login_required`, JWT/OIDC auth | Add FastAPI dependency; `MyBearerTokenValidator` is reusable |
| `api/device.py` (1414 lines) | Largest API file, 20 Resource classes | Split across PR 5-6 |
| `run.py` (178 lines) | App entry point, gevent, websocket thread | Switch to gunicorn+uvicorn in PR 9 |
| `pyproject.toml` | Dependencies | Add FastAPI deps in PR 1, remove Flask deps in PR 9 |

## Verification Plan

For each PR:
1. Run existing unit tests: `pytest src/ -m "not integration and not equipment"`
2. Run integration tests against FastAPI app: `pytest src/ -m integration`
3. Manual smoke test: start app, hit key endpoints with curl, verify response format
4. Compare OpenAPI spec output between Flask-RESTX and FastAPI docs

Final verification (PR 9):
1. Full test suite passes
2. Docker build and deployment works with uvicorn
3. WebSocket connections work
4. JWT and OIDC auth flows work end-to-end
