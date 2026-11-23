from abc import ABC, abstractmethod

from cnaas_nms.db.device import Device, DeviceType


class FirmwareException(Exception):
    """Base class for firmware related exceptions."""


class FirmwareAlreadyActiveException(FirmwareException):
    """Raised by FirmwareDriver.activate if the firmware is already the active one."""


class FirmwareDriver(ABC):
    """Base class for platform specific firmware upgrade drivers.

    Drivers are provided through the firmware_drivers plugin hook, both for the
    built-in drivers and for out-of-tree plugins. Exactly one driver may handle
    each platform.

    The pre_flight, download, activate and reload methods are Nornir tasks: they are
    run with task.run(task=driver.method, ...) and receive the Nornir task as their
    first argument. They should call set_thread_data(job_id) and honor job abort
    status like other job tasks.
    """

    #: Value of Device.platform that this driver handles, for example "eos"
    platform: str

    def resolve_image(self, dev: Device, filename: str) -> str:
        """Translate the requested firmware filename to the image file to use on a specific device.

        Can for example select a CPU architecture specific image. The default is to use the filename as is.
        """
        return filename

    def pre_flight(self, task, job_id: int | None = None) -> str:  # type: ignore
        """Nornir task to run checks and preparations before the upgrade. Does nothing by default."""
        return "No pre-flight checks for this platform."

    @abstractmethod
    def download(
        self,
        task,
        filename: str,
        httpd_url: str,
        device_type: DeviceType,
        job_id: int | None = None,  # type: ignore
    ) -> str:
        """Nornir task to download the firmware image from the NMS HTTP server to the device."""

    @abstractmethod
    def activate(self, task, filename: str, job_id: int | None = None) -> str:  # type: ignore
        """Nornir task to make the device boot the firmware image on next reload.

        Must raise FirmwareAlreadyActiveException if the image is already active.
        """

    @abstractmethod
    def reload(self, task, job_id: int | None = None) -> str:  # type: ignore
        """Nornir task to reload the device. The connection to the device is expected to be lost."""
