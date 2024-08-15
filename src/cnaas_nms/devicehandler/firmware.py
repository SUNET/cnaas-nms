import datetime
import time
from typing import Optional

from nornir.core.exceptions import NornirSubTaskError
from nornir.core.task import MultiResult
from nornir_napalm.plugins.tasks import napalm_cli, napalm_get
from nornir_netmiko.tasks import netmiko_send_command

from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.job import Job
from cnaas_nms.db.session import redis_session, sqla_session
from cnaas_nms.devicehandler.nornir_helper import NornirJobResult, cnaas_init, inventory_selector
from cnaas_nms.devicehandler.sync_history import add_sync_event
from cnaas_nms.scheduler.thread_data import set_thread_data
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.tools.log import get_logger


class FirmwareAlreadyActiveException(Exception):
    pass


def arista_pre_flight_check(task, job_id: Optional[int] = None) -> str:
    """
    NorNir task to do some basic checks before attempting to upgrade a switch.

    Args:
        task: NorNir task

    Returns:
        String, describing the result

    """
    set_thread_data(job_id)
    logger = get_logger()
    with sqla_session() as session:
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


def arista_post_flight_check(task, post_waittime: int, scheduled_by: str, job_id: Optional[int] = None) -> str:
    """
    NorNir task to update device facts after a switch have been upgraded

    Args:
        task: NorNir task
        post_waittime: Time to wait before trying to gather facts
        scheduled_by: Who scheduled the job
        job_id: Job ID

    Returns:
        String, describing the result

    """
    set_thread_data(job_id)
    logger = get_logger()
    time.sleep(int(post_waittime))
    logger.info("Post-flight check wait ({}s) complete, starting check for {}".format(post_waittime, task.host.name))
    with sqla_session() as session:
        if Job.check_job_abort_status(session, job_id):
            return "Post-flight aborted"

    try:
        res = task.run(napalm_get, getters=["facts"])
        os_version = res[0].result["facts"]["os_version"]

        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.hostname == task.host.name).one()
            prev_os_version = dev.os_version
            dev.os_version = os_version
            if prev_os_version == os_version:
                logger.error("OS version did not change, activation failed on {}".format(task.host.name))
                raise Exception("OS version did not change, activation failed")
            else:
                dev.confhash = None
                dev.synchronized = False
                add_sync_event(task.host.name, "firmware_upgrade", scheduled_by, job_id)
                dev.last_seen = datetime.datetime.utcnow()
    except Exception as e:
        logger.exception("Could not update OS version on device {}: {}".format(task.host.name, str(e)))
        return "Post-flight failed, could not update OS version: {}".format(str(e))

    return "Post-flight, OS version updated from {} to {}.".format(prev_os_version, os_version)


def arista_firmware_download(task, filename: str, httpd_url: str, job_id: Optional[int] = None) -> str:
    """
    NorNir task to download firmware image from the HTTP server.

    Args:
        task: NorNir task
        filename: Name of the file to download
        httpd_url: Base URL to the HTTP server
        job_id: Job ID

    Returns:
        String, describing the result

    """
    set_thread_data(job_id)
    logger = get_logger()
    with sqla_session() as session:
        if Job.check_job_abort_status(session, job_id):
            return "Firmware download aborted"

    url = httpd_url + "/" + filename

    try:
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.hostname == task.host.name).one_or_none()
            device_type = dev.device_type

        if device_type == DeviceType.ACCESS:
            firmware_download_cmd = "copy {} flash:".format(url)
        else:
            firmware_download_cmd = "copy {} vrf MGMT flash:".format(url)

        res = task.run(
            netmiko_send_command, command_string=firmware_download_cmd.replace("//", "/"), enable=True, read_timeout=500
        )

        if "Copy completed successfully" in res.result:
            return "Firmware download done."
        else:
            logger.debug(
                "Firmware download failed on {} ('{}'): {}".format(task.host.name, firmware_download_cmd, res.result)
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


def arista_firmware_activate(task, filename: str, job_id: Optional[int] = None) -> str:
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
    with sqla_session() as session:
        if Job.check_job_abort_status(session, job_id):
            return "Firmware activate aborted"

    try:
        boot_file_cmd = "boot system flash:{}".format(filename)

        res = task.run(netmiko_send_command, command_string="enable", expect_string=".*#")

        res = task.run(netmiko_send_command, command_string='show boot-config | grep -o "\\w*{}\\w*"'.format(filename))
        if res.result == filename:
            raise FirmwareAlreadyActiveException(
                "Firmware already activated in boot-config on {}".format(task.host.name)
            )

        res = task.run(netmiko_send_command, command_string="conf t", expect_string=".*config.*#")

        res = task.run(netmiko_send_command, command_string=boot_file_cmd, read_timeout=120)

        res = task.run(netmiko_send_command, command_string="end", expect_string=".*#")

        res = task.run(netmiko_send_command, command_string='show boot-config | grep -o "\\w*{}\\w*"'.format(filename))

        if not isinstance(res, MultiResult):
            raise Exception("Could not check boot-config on {}".format(task.host.name))

        if res.result != filename:
            raise Exception("Firmware not activated properly on {}".format(task.host.name))
    except FirmwareAlreadyActiveException as e:
        raise e
    except Exception as e:
        logger.exception("Failed to activate firmware on {}: {}".format(task.host.name, str(e)))
        raise Exception("Failed to activate firmware")

    return "Firmware activate done."


def arista_device_reboot(task, job_id: Optional[int] = None) -> str:
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
    with sqla_session() as session:
        if Job.check_job_abort_status(session, job_id):
            return "Reboot aborted"

    try:
        task.run(netmiko_send_command, command_string="enable", expect_string=".*#")

        task.run(netmiko_send_command, command_string="write", expect_string=".*#")

        task.run(netmiko_send_command, command_string="reload force", max_loops=2, expect_string=".*")
    except Exception as e:  # noqa: S110
        logger.exception("Failed to reboot switch {}: {}".format(task.host.name, str(e)))
        raise e

    return "Device reboot done."


def device_upgrade_task(
    task,
    job_id: int,
    scheduled_by: str,
    filename: str,
    url: str,
    reboot: Optional[bool] = False,
    download: Optional[bool] = False,
    pre_flight: Optional[bool] = False,
    post_flight: Optional[bool] = False,
    post_waittime: Optional[int] = 0,
    activate: Optional[bool] = False,
) -> NornirJobResult:
    # If pre-flight is selected, execute the pre-flight task which
    # will verify the amount of disk space and so on.
    set_thread_data(job_id)
    logger = get_logger()
    if pre_flight:
        logger.info("Running pre-flight check on {}".format(task.host.name))
        try:
            res = task.run(task=arista_pre_flight_check, job_id=job_id)
        except Exception as e:
            logger.exception("Exception while doing pre-flight check: {}".format(str(e)))
            raise Exception("Pre-flight check failed")
        else:
            if res.failed:
                logger.exception("Pre-flight check failed for: {}".format(" ".join(res.failed_hosts.keys())))
                raise

    # If download is true, go ahead and download the firmware
    if download:
        # Download the firmware from the HTTP container.
        logger.info("Downloading firmware {} on {}".format(filename, task.host.name))
        try:
            res = task.run(task=arista_firmware_download, filename=filename, httpd_url=url, job_id=job_id)
        except Exception as e:
            logger.exception("Exception while downloading firmware: {}".format(str(e)))
            raise e

    # If download_only is false, continue to activate the newly downloaded
    # firmware and verify that it if present in the boot-config.
    already_active = False
    if activate:
        logger.info("Activating firmware {} on {}".format(filename, task.host.name))
        try:
            res = task.run(task=arista_firmware_activate, filename=filename, job_id=job_id)
        except NornirSubTaskError as e:
            subtask_result = e.result[0]
            logger.debug("Exception while activating firmware for {}: {}".format(task.host.name, subtask_result))
            if subtask_result.exception:
                if isinstance(subtask_result.exception, FirmwareAlreadyActiveException):
                    already_active = True
                    logger.info(
                        "Firmware already active, skipping reboot and post_flight: {}".format(subtask_result.exception)
                    )
                else:
                    logger.exception(
                        "Firmware activate subtask exception for {}: {}".format(
                            task.host.name, str(subtask_result.exception)
                        )
                    )
                    raise e
            else:
                logger.error("Activate subtask result for {}: {}".format(task.host.name, subtask_result.result))
                raise e
        except Exception as e:
            logger.exception("Exception while activating firmware for {}: {}".format(task.host.name, str(e)))
            raise e

    # Reboot the device if needed, we will then lose the connection.
    if reboot and not already_active:
        logger.info("Rebooting {}".format(task.host.name))
        try:
            res = task.run(task=arista_device_reboot, job_id=job_id)
        except Exception:  # noqa: S110
            pass

    # If post-flight is selected, execute the post-flight task which
    # will update device facts for the selected devices
    if post_flight and not already_active:
        logger.info("Running post-flight check on {}, delay start by {}s".format(task.host.name, post_waittime))
        try:
            res = task.run(
                task=arista_post_flight_check, post_waittime=post_waittime, scheduled_by=scheduled_by, job_id=job_id
            )
        except Exception as e:
            logger.exception("Failed to run post-flight check: {}".format(str(e)))
        else:
            if res.failed:
                logger.error("Post-flight check failed for: {}".format(" ".join(res.failed_hosts.keys())))

    if job_id:
        with redis_session() as db:
            db.lpush("finished_devices_" + str(job_id), task.host.name)


@job_wrapper
def device_upgrade(
    download: Optional[bool] = False,
    activate: Optional[bool] = False,
    filename: Optional[bool] = None,
    group: Optional[str] = None,
    hostname: Optional[str] = None,
    url: Optional[str] = None,
    job_id: Optional[int] = None,
    pre_flight: Optional[bool] = False,
    post_flight: Optional[bool] = False,
    post_waittime: Optional[int] = 600,
    reboot: Optional[bool] = False,
    scheduled_by: Optional[str] = None,
) -> NornirJobResult:
    logger = get_logger()
    nr = cnaas_init()
    if hostname:
        nr_filtered, dev_count, _ = inventory_selector(nr, hostname=hostname)
    elif group:
        nr_filtered, dev_count, _ = inventory_selector(nr, group=group)
    else:
        raise ValueError("Neither hostname nor group specified for device_upgrade")

    device_list = list(nr_filtered.inventory.hosts.keys())
    logger.info("Device(s) selected for firmware upgrade ({}): {}".format(dev_count, ", ".join(device_list)))
    logger.info(
        f"Upgrade tasks selected: pre_flight = {pre_flight}, download = {download}, "
        + f"activate = {activate}, reboot = {reboot}, post_flight = {post_flight}"
    )

    # Make sure we only upgrade Arista access switches
    for device in device_list:
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.hostname == device).one_or_none()
            if not dev:
                raise Exception("Could not find device: {}".format(device))
            if dev.platform != "eos":
                raise Exception('Invalid device platform "{}" for device: {}'.format(dev.platform, device))

    # Start tasks to take care of the upgrade
    try:
        nrresult = nr_filtered.run(
            task=device_upgrade_task,
            job_id=job_id,
            scheduled_by=scheduled_by,
            download=download,
            filename=filename,
            url=url,
            pre_flight=pre_flight,
            post_flight=post_flight,
            post_waittime=post_waittime,
            reboot=reboot,
            activate=activate,
        )
    except Exception as e:
        logger.exception("Exception while upgrading devices: {}".format(str(e)))
        return NornirJobResult(nrresult=nrresult)

    failed_hosts = list(nrresult.failed_hosts.keys())
    for hostname in failed_hosts:
        logger.error("Firmware upgrade of device '{}' failed".format(hostname))

    if nrresult.failed:
        logger.error("Not all devices were successfully upgraded")

    return NornirJobResult(nrresult=nrresult)
