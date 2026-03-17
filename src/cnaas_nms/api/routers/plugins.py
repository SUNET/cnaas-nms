from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cnaas_nms.api.dependencies import get_current_user
from cnaas_nms.api.response import CnaasJSONResponse, empty_result
from cnaas_nms.plugins.pluginmanager import PluginManagerHandler

router = APIRouter(tags=["plugins"])


class PluginAction(BaseModel):
    action: str


@router.get("/plugins")
def get_plugins(user: str = Depends(get_current_user)):
    """List all plugins."""
    try:
        pmh = PluginManagerHandler()
        plugindata = pmh.get_plugindata()
        plugin_module_names = pmh.get_plugins()
    except Exception as e:
        return CnaasJSONResponse(
            content=empty_result("error", "Error retrieving plugins {}".format(str(e)))
        )
    else:
        return empty_result("success", {"loaded_plugins": plugin_module_names, "plugindata": plugindata})


@router.put("/plugins")
def modify_plugins(plugin_action: PluginAction, user: str = Depends(get_current_user)):
    """Modify plugins."""
    if str(plugin_action.action).upper() == "SELFTEST":
        pmh = PluginManagerHandler()
        res = pmh.pm.hook.selftest()
        return empty_result("success", {"result": res})
    else:
        return CnaasJSONResponse(
            status_code=400,
            content=empty_result("error", "Unknown action specified"),
        )
