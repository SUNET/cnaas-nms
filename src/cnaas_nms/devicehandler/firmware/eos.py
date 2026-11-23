from typing import Optional

from nornir.core.exceptions import NornirSubTaskError
from nornir.core.task import MultiResult
from nornir_napalm.plugins.tasks import napalm_cli
from nornir_netmiko.tasks import netmiko_send_command

from cnaas_nms.db.device import CpuArchitecture, Device, DeviceType
from cnaas_nms.db.job import Job
from cnaas_nms.db.session import sqla_session
from cnaas_nms.devicehandler.firmware.base import FirmwareAlreadyActiveException, FirmwareDriver
from cnaas_nms.devicehandler.os_specifics.arista_models import detect_arch
from cnaas_nms.scheduler.thread_data import set_thread_data
from cnaas_nms.tools.log import get_logger


class EOSFirmwareDriver(FirmwareDriver):
    """Firmware upgrades for Arista EOS."""

    platform = "eos"

    def resolve_image(self, dev: Device, filename: str) -> str:
        filename = filename.removeprefix("detect_arch-")  # For backward compatibility
        _, version = filename.split("-", 1)
        logger = get_logger()
        # Prefer the persisted cpu_arch (set by update_facts, and possibly
        # manually overridden in the DB) over re-deriving it from the model,
        # so a stored value is always respected.
        arch = dev.cpu_arch if dev.cpu_arch is not None else detect_arch(dev)

        if arch == CpuArchitecture.X86_32:
            filename = "EOS-" + version
            logger.info("Detected 32-bit device {}, selecting 32-bit version: {}".format(dev.hostname, filename))
        elif arch == CpuArchitecture.ARM64:
            filename = "EOSarm-" + version
            logger.info("Detected ARM device {}, selecting ARM version: {}".format(dev.hostname, filename))
        else:
            # Default to 64-bit if architecture is unknown or 64-bit
            filename = "EOS64-" + version
            logger.info("Detected 64-bit device {}, selecting 64-bit version: {}".format(dev.hostname, filename))
        return filename

    def pre_flight(self, task, job_id: Optional[int] = None) -> str:  # type: ignore
        """
        NorNir task to do some basic checks before attempting to upgrade a switch.

        Args:
            task: NorNir task

        Returns:
            String, describing the result

        """
        set_thread_data(job_id)
        logger = get_logger()
        with sqla_session() as session:  # type: ignore
            if Job.check_job_abort_status(session, job_id):
                return "Pre-flight aborted"

        flash_diskspace = "bash timeout 5 df /mnt/flash | awk '{print $4}'"
        flash_cleanup = 'bash timeout 30 ls -t /mnt/flash/*.swi | tail -n +2 | grep -v `cut -d"/" -f2 /mnt/flash/boot-config` | xargs rm -f'

        # Get amount of free disk space
        res = task.run(napalm_cli, commands=[flash_diskspace])
        if not isinstance(res, MultiResult) or len(res.result.keys()) != 1:
            raise Exception("Could not check free space")

        # Remove old firmware images if needed
        free_bytes = next(iter(res.result.values())).split("\n")[1]
        if int(free_bytes) < 2500000:
            logger.info("Cleaning up old firmware images on {}".format(task.host.name))
            res = task.run(napalm_cli, commands=[flash_cleanup])
        else:
            logger.info("Enough free space ({}b), no cleanup".format(free_bytes))

        return "Pre-flight check done."

    def download(
        self,
        task,
        filename: str,
        httpd_url: str,
        device_type: DeviceType,
        job_id: Optional[int] = None,  # type: ignore
    ) -> str:
        """
        NorNir task to download firmware image from the HTTP server.

        Args:
            task: NorNir task
            filename: Name of the file to download
            httpd_url: Base URL to the HTTP server
            device_type: Device type
            job_id: Job ID

        Returns:
            String, describing the result

        """
        set_thread_data(job_id)
        logger = get_logger()
        with sqla_session() as session:  # type: ignore
            if Job.check_job_abort_status(session, job_id):
                return "Firmware download aborted"

        try:
            url = httpd_url + "/" + filename

            if device_type == DeviceType.ACCESS:
                firmware_download_cmd = "copy {} flash:".format(url)
            else:
                firmware_download_cmd = "copy {} vrf MGMT flash:".format(url)

            res = task.run(
                netmiko_send_command,
                command_string=firmware_download_cmd.replace("//", "/"),
                enable=True,
                read_timeout=500,
            )

            if "Copy completed successfully" in res.result:
                return "Firmware download done."
            else:
                logger.error(
                    "Firmware download failed on {} ('{}'): {}".format(
                        task.host.name, firmware_download_cmd, res.result
                    )
                )
                raise Exception(
                    "Copy command did not complete successfully: {}".format(
                        ", ".join(filter(lambda x: x.startswith("get:"), res.result.splitlines()))
                    )
                )

        except NornirSubTaskError as e:
            subtask_result = e.result[0]
            logger.error("{} failed to download firmware: {}".format(task.host.name, subtask_result))
            logger.debug("{} download subtask result: {}".format(task.host.name, subtask_result.result))
            raise Exception("Failed to download firmware: {}".format(subtask_result))
        except Exception as e:
            logger.error("{} failed to download firmware: {}".format(task.host.name, e))
            raise Exception("Failed to download firmware: {}".format(e))

        return "Firmware download done."

    def activate(self, task, filename: str, job_id: Optional[int] = None) -> str:  # type: ignore
        """
        NorNir task to modify the boot config for new firmwares.

        Args:
            task: NorNir task
            filename: Name of the new firmware image
            job_id: Job ID

        Returns:
            String, describing the result

        """
        set_thread_data(job_id)
        logger = get_logger()
        with sqla_session() as session:  # type: ignore
            if Job.check_job_abort_status(session, job_id):
                return "Firmware activate aborted"

        try:
            boot_file_cmd = "boot system flash:{}".format(filename)

            task.run(netmiko_send_command, command_string="enable", expect_string=".*#")

            res = task.run(
                netmiko_send_command, command_string='show boot-config | grep -o "\\w*{}\\w*"'.format(filename)
            )
            if res.result == filename:
                raise FirmwareAlreadyActiveException(
                    "Firmware already activated in boot-config on {}".format(task.host.name)
                )

            task.run(netmiko_send_command, command_string="conf t", expect_string=".*config.*#")

            res = task.run(netmiko_send_command, command_string=boot_file_cmd, read_timeout=300)

            if not isinstance(res, MultiResult):
                raise Exception("Could not activate firmware on {}".format(task.host.name))

            if res.result:
                logger.error("Error when activating firmware on {}: {}".format(task.host.name, res.result))

            task.run(netmiko_send_command, command_string="end", expect_string=".*#")

            res = task.run(
                netmiko_send_command, command_string='show boot-config | grep -o "\\w*{}\\w*"'.format(filename)
            )

            if not isinstance(res, MultiResult):
                raise Exception("Could not check boot-config on {}".format(task.host.name))

            if res.result != filename:
                raise Exception("Firmware not activated properly on {}".format(task.host.name))
        except FirmwareAlreadyActiveException as e:
            raise e
        except Exception as e:
            logger.exception("Failed to activate firmware on {}: {}".format(task.host.name, str(e)))
            raise Exception("Failed to activate firmware")

        return "Firmware {} activation done.".format(filename)

    def reload(self, task, job_id: Optional[int] = None) -> str:  # type: ignore
        """
        NorNir task to reboot a single device.

        Args:
            task: NorNir task.
            job_id: Job ID

        Returns:
            String, describing the result

        """
        set_thread_data(job_id)
        logger = get_logger()
        with sqla_session() as session:  # type: ignore
            if Job.check_job_abort_status(session, job_id):
                return "Reboot aborted"

        try:
            task.run(netmiko_send_command, command_string="enable", expect_string=".*#")

            task.run(netmiko_send_command, command_string="write", expect_string=".*#")

            res = task.run(netmiko_send_command, command_string="reload force", max_loops=2, expect_string=".*")

            if not isinstance(res, MultiResult):
                raise Exception("Could not reboot device {}".format(task.host.name))

            if res.result:
                logger.error("Error when rebooting device {}: {}".format(task.host.name, res.result))
        except Exception as e:  # noqa: S110
            logger.exception("Failed to reboot switch {}: {}".format(task.host.name, str(e)))
            raise e

        return "Device reboot done."
