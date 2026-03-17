import json
from ipaddress import _IPAddressBase
from typing import Any, Dict

from fastapi.responses import JSONResponse


def empty_result(status: str = "success", data: Any = None) -> Dict[str, Any]:
    """Standard CNaaS response envelope, framework-agnostic."""
    if status == "success":
        return {"status": status, "data": data}
    elif status == "error":
        return {"status": status, "message": data if data else "Unknown error"}
    else:
        return {}


class CnaasJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles IP address objects."""

    def default(self, o: Any) -> Any:
        if isinstance(o, _IPAddressBase):
            return str(o)
        if hasattr(o, "as_dict"):
            return o.as_dict()
        return super().default(o)


class CnaasJSONResponse(JSONResponse):
    """JSONResponse subclass that serializes IP addresses to strings."""

    def render(self, content: Any) -> bytes:
        return json.dumps(content, cls=CnaasJSONEncoder, ensure_ascii=False).encode("utf-8")
