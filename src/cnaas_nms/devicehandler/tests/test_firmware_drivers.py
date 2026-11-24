import pytest

from cnaas_nms.db.device import CpuArchitecture, Device
from cnaas_nms.devicehandler.firmware.base import FirmwareDriver
from cnaas_nms.devicehandler.firmware.eos import EOSFirmwareDriver
from cnaas_nms.devicehandler.firmware.registry import get_firmware_driver, get_firmware_drivers
from cnaas_nms.plugins.pluginmanager import PluginManagerHandler
from cnaas_nms.plugins.pluginspec import hookimpl


class DummyDriver(FirmwareDriver):
    platform = "dummy"

    def download(self, task, filename, httpd_url, device_type, job_id=None):
        return "download"

    def activate(self, task, filename, job_id=None):
        return "activate"

    def reload(self, task, job_id=None):
        return "reload"


class DuplicateEOSDriver(DummyDriver):
    platform = "eos"


def make_plugin(*driver_classes):
    class Plugin:
        @hookimpl
        def firmware_drivers(self):
            return list(driver_classes)

    return Plugin()


@pytest.fixture
def plugin_manager():
    pm = PluginManagerHandler().pm
    registered = []

    def register(plugin):
        pm.register(plugin)
        registered.append(plugin)

    yield register
    for plugin in registered:
        pm.unregister(plugin)


def test_builtin_eos_driver_is_loaded():
    assert isinstance(get_firmware_driver("eos"), EOSFirmwareDriver)


def test_plugin_can_provide_driver(plugin_manager):
    plugin_manager(make_plugin(DummyDriver))
    assert isinstance(get_firmware_driver("dummy"), DummyDriver)
    assert "eos" in get_firmware_drivers()


def test_duplicate_platform_is_rejected(plugin_manager):
    plugin_manager(make_plugin(DuplicateEOSDriver))
    with pytest.raises(ValueError, match="Multiple firmware drivers for platform eos"):
        get_firmware_drivers()


@pytest.mark.parametrize("platform", ["nonexistent", "", None])
def test_unknown_platform(platform):
    with pytest.raises(ValueError, match="No firmware upgrade driver"):
        get_firmware_driver(platform)


@pytest.mark.parametrize(
    "cpu_arch,filename,expected",
    [
        (CpuArchitecture.X86_32, "EOS-4.31.2F", "EOS-4.31.2F"),
        (CpuArchitecture.X86_64, "EOS-4.31.2F", "EOS64-4.31.2F"),
        (CpuArchitecture.ARM64, "EOS64-4.31.2F", "EOSarm-4.31.2F"),
        (CpuArchitecture.X86_64, "detect_arch-EOS-4.31.2F", "EOS64-4.31.2F"),
    ],
)
def test_eos_resolve_image(cpu_arch, filename, expected):
    dev = Device(hostname="eosdist1", cpu_arch=cpu_arch)
    assert EOSFirmwareDriver().resolve_image(dev, filename) == expected
