from cnaas_nms.devicehandler.firmware.base import FirmwareDriver
from cnaas_nms.devicehandler.firmware.eos import EOSFirmwareDriver
from cnaas_nms.plugins.pluginspec import hookimpl


class BuiltinFirmwareDrivers:
    """Plugin providing the firmware drivers that are included with CNaaS-NMS.

    Registered automatically by PluginManagerHandler, in the same way as out-of-tree
    plugins provide their drivers.
    """

    @hookimpl
    def firmware_drivers(self) -> list[type[FirmwareDriver]]:
        return [EOSFirmwareDriver]
