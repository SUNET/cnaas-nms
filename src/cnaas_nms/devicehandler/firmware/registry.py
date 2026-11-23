from typing import Optional

from cnaas_nms.devicehandler.firmware.base import FirmwareDriver
from cnaas_nms.plugins.pluginmanager import PluginManagerHandler


def get_firmware_drivers() -> dict[str, FirmwareDriver]:
    """Collect firmware drivers from all loaded plugins, keyed by platform."""
    drivers: dict[str, FirmwareDriver] = {}
    for driver_classes in PluginManagerHandler().pm.hook.firmware_drivers():
        for driver_class in driver_classes or []:
            driver = driver_class()
            if driver.platform in drivers:
                raise ValueError(
                    "Multiple firmware drivers for platform {}: {} and {}".format(
                        driver.platform, type(drivers[driver.platform]).__name__, driver_class.__name__
                    )
                )
            drivers[driver.platform] = driver
    return drivers


def get_firmware_driver(platform: Optional[str]) -> FirmwareDriver:
    """Get the firmware driver for a platform, raises ValueError if there is none."""
    driver = get_firmware_drivers().get(platform) if platform else None
    if driver is None:
        raise ValueError('No firmware upgrade driver available for platform "{}"'.format(platform))
    return driver
