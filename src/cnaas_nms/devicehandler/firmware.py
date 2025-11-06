import datetime
import time
from typing import Dict, List, Optional

from nornir.core import AggregatedResult
from nornir.core.exceptions import NornirSubTaskError
from nornir.core.task import MultiResult
from nornir_napalm.plugins.tasks import napalm_cli, napalm_get
from nornir_netmiko.tasks import netmiko_send_command

from cnaas_nms.db.device import Device, DeviceType
from cnaas_nms.db.job import Job
from cnaas_nms.db.session import redis_session, sqla_session
from cnaas_nms.db.settings import get_settings
from cnaas_nms.devicehandler.nornir_helper import NornirJobResult, cnaas_init, inventory_selector
from cnaas_nms.devicehandler.os_specifics import arista_models
from cnaas_nms.devicehandler.sync_history import add_sync_event
from cnaas_nms.devicehandler.upgradeorder import determine_upgrade_order
from cnaas_nms.plugins.pluginmanager import PluginManagerHandler
from cnaas_nms.scheduler.thread_data import set_thread_data
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.tools.log import get_logger


class FirmwareAlreadyActiveException(Exception):
    pass


def arista_pre_flight_check(task, job_id: Optional[int] = None) -> str:  # type: ignore
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


def arista_post_flight_check(
    task,
    post_waittime: Optional[int],
    dev_settings: Dict,
    device_model: str,
    scheduled_by: str,
    job_id: Optional[int] = None,
) -> str:
    """
    NorNir task to update device facts after a switch have been upgraded

    Args:
        task: NorNir task
        post_waittime: Time to wait before trying to gather facts
        dev_settings: Device settings from get_settings()
        device_model: Device model string
        scheduled_by: Who scheduled the job
        job_id: Job ID

    Returns:
        String, describing the result

    """
    set_thread_data(job_id)
    logger = get_logger()
    post_waittime_source: str = "API call"
    if post_waittime is None:
        waittime_dict: Dict[str, int] = dev_settings.get("upgrade_post_waittime", {})
        post_waittime_model = waittime_dict.get(device_model, None)
        if post_waittime_model is not None:
            post_waittime = post_waittime_model
            post_waittime_source = "Settings -> Device model"

    if post_waittime is None:
        post_waittime_platform = waittime_dict.get(task.host.platform, None)
        if post_waittime_platform is not None:
            post_waittime = post_waittime_platform
            post_waittime_source = "Settings -> Device platform"

    if post_waittime is None:
        post_waittime = waittime_dict.get("default", 600)
        post_waittime_source = "Settings -> Default"

    # make sure post_waittime is longer than 0 seconds and shorter than 24 hours
    post_waittime = max(min(post_waittime, 86400), 0)
    logger.info(
        "Running post-flight check on {}, delay start by {}s (delay time from {})".format(
            task.host.name, post_waittime, post_waittime_source
        )
    )
    time.sleep(int(post_waittime))
    with sqla_session() as session:  # type: ignore
        if Job.check_job_abort_status(session, job_id):
            return "Post-flight aborted"
    logger.info(
        "post_waittime has passed ({}s), beginning post-flight check for {}".format(post_waittime, task.host.name)
    )

    try:
        # retry once per minute for post_waittime / 2 or 30 retries, whichever is lower
        max_attempts = min(round((post_waittime / 2) / 60), 30) + 1
        os_version: Optional[str] = None
        for i in range(0, max_attempts):
            start_time = time.time()
            res: Optional[MultiResult] = None
            try:
                res = task.run(napalm_get, getters=["facts"])
            except NornirSubTaskError:
                # We don't want to fail the parent task if one connection attempt fails
                if task.results[-1].name == "napalm_get":
                    task.results[-1].failed = False
            else:
                if isinstance(res, MultiResult) and not res.failed:
                    logger.debug("Device {} responsive on check attempt {}".format(task.host.name, i + 1))
                    os_version = res[0].result["facts"]["os_version"]
                    break
            time.sleep(max(60 - (time.time() - start_time), 0))

        if not os_version:
            raise Exception("Device {} did not respond to check".format(task.host.name))

        with sqla_session() as session:  # type: ignore
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
                dev.last_seen = datetime.datetime.utcnow()  # type: ignore
    except Exception as e:
        logger.exception("Could not update OS version on device {}: {}".format(task.host.name, str(e)))
        raise e

    return "Post-flight, OS version updated from {} to {}.".format(prev_os_version, os_version)


def arista_firmware_download(
    task, filename: str, httpd_url: str, device_type: DeviceType, job_id: Optional[int] = None
) -> str:
    """
    NorNir task to download firmware image from the HTTP server.

    Args:
        task: NorNir task
        filename: Name of the file to download
        httpd_url: Base URL to the HTTP server
        device_type: Device type
        job_id: Job ID
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


def arista_firmware_activate(task, filename: str, job_id: Optional[int] = None) -> str:  # type: ignore
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

        res = task.run(netmiko_send_command, command_string='show boot-config | grep -o "\\w*{}\\w*"'.format(filename))
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

    return "Firmware {} activation done.".format(filename)


def arista_device_reboot(task, job_id: Optional[int] = None) -> str:  # type: ignore
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
            logger.debug("Error when rebooting device {}: {}".format(task.host.name, res.result))
    except Exception as e:  # noqa: S110
        logger.exception("Failed to reboot switch {}: {}".format(task.host.name, str(e)))
        raise e

    return "Device reboot done."


def device_upgrade_task(
    task,  # type: ignore
    job_id: int,
    scheduled_by: str,
    filename: Optional[str],
    url: str,
    reboot: Optional[bool] = False,
    download: Optional[bool] = False,
    pre_flight: Optional[bool] = False,
    post_flight: Optional[bool] = False,
    post_waittime: Optional[int] = None,
    activate: Optional[bool] = False,
) -> str:
    # If pre-flight is selected, execute the pre-flight task which
    # will verify the amount of disk space and so on.
    set_thread_data(job_id)
    logger = get_logger()
    with sqla_session() as session:  # type: ignore
        dev: Optional[Device] = session.query(Device).filter(Device.hostname == task.host.name).one_or_none()
        if not dev:
            raise Exception("Could not find a device with hostname {}".format(task.host.name))
        device_type = dev.device_type
        device_model = dev.model
        session.expunge(dev)

    if filename and filename.startswith("detect_arch-"):
        dev_settings, _ = get_settings(dev, device_type)
        if dev_settings and "arista_models_32bit" in dev_settings and dev_settings["arista_models_32bit"] is not None:
            models_32bit: List[str] = dev_settings["arista_models_32bit"]
        else:
            models_32bit = arista_models.models_32bit
        filename = filename.removeprefix("detect_arch-")
        if device_model in models_32bit and filename.startswith("EOS64-"):
            filename = "EOS-" + filename.removeprefix("EOS64-")
            logger.info(
                "Detected 32-bit device {}, changing filename to 32-bit version: {}".format(task.host.name, filename)
            )
        elif device_model not in models_32bit and filename.startswith("EOS-"):
            filename = "EOS64-" + filename.removeprefix("EOS-")
            logger.info(
                "Detected 64-bit device {}, changing filename to 64-bit version: {}".format(task.host.name, filename)
            )

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
        if not filename:
            raise Exception("No filename specified for download")
        # Download the firmware from the HTTP container.
        logger.info("Downloading firmware {} on {}".format(filename, task.host.name))
        try:
            res = task.run(
                task=arista_firmware_download, filename=filename, httpd_url=url, device_type=device_type, job_id=job_id
            )
        except Exception as e:
            logger.exception("Exception while downloading firmware: {}".format(str(e)))
            raise e

    # If download_only is false, continue to activate the newly downloaded
    # firmware and verify that it if present in the boot-config.
    already_active = False
    if activate:
        if not filename:
            raise Exception("No filename specified for activate")
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
            pmh = PluginManagerHandler()
            pmh.pm.hook.upgrade_reboot_starting(hostname=task.host.name)
        except Exception as e:
            logger.exception("Error while running plugin hooks for upgrade_reboot_starting: {}".format(str(e)))
        try:
            res = task.run(task=arista_device_reboot, job_id=job_id)
        except Exception:  # noqa: S110
            pass

    # If post-flight is selected, execute the post-flight task which
    # will update device facts for the selected devices
    if post_flight and not already_active:
        try:
            dev_settings, _ = get_settings(dev, device_type)
            res = task.run(
                task=arista_post_flight_check,
                post_waittime=post_waittime,
                scheduled_by=scheduled_by,
                job_id=job_id,
                dev_settings=dev_settings,
                device_model=device_model,
            )
        except Exception as e:
            logger.exception("Failed to run post-flight check: {}".format(str(e)))
            try:
                pmh = PluginManagerHandler()
                pmh.pm.hook.upgrade_reboot_completed(hostname=task.host.name, failed=True)
            except Exception as e:
                logger.exception("Error while running plugin hooks for upgrade_reboot_completed: {}".format(str(e)))
        else:
            if res.failed:
                logger.error("Post-flight check failed for: {}".format(" ".join(res.failed_hosts.keys())))
            try:
                pmh = PluginManagerHandler()
                pmh.pm.hook.upgrade_reboot_completed(hostname=task.host.name, failed=res.failed)
            except Exception as e:
                logger.exception("Error while running plugin hooks for upgrade_reboot_completed: {}".format(str(e)))

    if job_id:
        with redis_session() as db:  # type: ignore
            db.lpush("finished_devices_" + str(job_id), task.host.name)

    return "Devices upgraded"


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
    post_waittime: Optional[int] = None,
    reboot: Optional[bool] = False,
    staggered_upgrade: Optional[bool] = False,
    scheduled_by: str = "",
) -> NornirJobResult:
    logger = get_logger()
    nr = cnaas_init()
    if hostname:
        nr_filtered_group, dev_count, _ = inventory_selector(nr, hostname=hostname)
    elif group:
        nr_filtered_group, dev_count, _ = inventory_selector(nr, group=group)
    else:
        raise ValueError("Neither hostname nor group specified for device_upgrade")

    device_hostname_list = list(nr_filtered_group.inventory.hosts.keys())
    logger.info("Device(s) selected for firmware upgrade ({}): {}".format(dev_count, ", ".join(device_hostname_list)))
    logger.info(
        f"Upgrade tasks selected: pre_flight = {pre_flight}, download = {download}, "
        + f"activate = {activate}, reboot = {reboot}, post_flight = {post_flight}"
    )

    # Make sure we only upgrade Arista access switches
    with sqla_session() as session:  # type: ignore
        upgrade_groups: list[list[str]] = []
        device_list: list[Device] = []
        for device in device_hostname_list:
            dev: Optional[Device] = session.query(Device).filter(Device.hostname == device).one_or_none()
            if not dev:
                raise Exception("Could not find device: {}".format(device))
            if dev.platform != "eos":
                raise Exception('Invalid device platform "{}" for device: {}'.format(dev.platform, device))
            device_list.append(dev)

        if reboot and len(device_list) > 1 and staggered_upgrade:
            upgrade_device_groups: list[list[Device]] = determine_upgrade_order(session, device_list)
            upgrade_groups = [[device.hostname for device in group] for group in upgrade_device_groups]
        else:
            staggered_upgrade = False
            upgrade_groups = [device_hostname_list]

    if staggered_upgrade:
        logger.info("Upgrade will be performed in {} steps(s)".format(len(upgrade_groups)))
        for i, upgrade_group in enumerate(upgrade_groups):
            logger.info("  Step {}: {}".format(i + 1, ", ".join(upgrade_group)))

    # Start tasks to take care of the upgrade
    failed_hosts: List[str] = []
    aggregated_result = AggregatedResult("device_upgrade")
    for i, upgrade_group in enumerate(upgrade_groups):
        nr_filtered_group, _, _ = inventory_selector(nr, hostname=upgrade_group)
        old_num_workers = nr_filtered_group.config.runner.options["num_workers"]
        try:
            nr_filtered_group.config.runner.options["num_workers"] = 10
            nrresult = nr_filtered_group.run(
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
            for k, v in nrresult.items():
                aggregated_result[k] = v
        except Exception as e:
            logger.exception("Exception while upgrading devices: {}".format(str(e)))
            return NornirJobResult(nrresult=aggregated_result)
        finally:
            nr_filtered_group.config.runner.options["num_workers"] = old_num_workers

        failed_hosts.extend(list(nrresult.failed_hosts.keys()))
        if nrresult.failed and i + 1 < len(upgrade_groups):
            logger.error(
                "Aborting staggered upgrade due to failures in step {}, failed devices: {}".format(
                    i + 1, ", ".join(nrresult.failed_hosts.keys())
                )
            )
            break
        with sqla_session() as session:  # type: ignore
            if Job.check_job_abort_status(session, job_id):
                logger.info("Firmware upgrade aborted by user")
                break
        if staggered_upgrade:
            logger.info(f"Upgrade group {i + 1} completed")

    for hostname in failed_hosts:
        logger.error("Firmware upgrade of device '{}' failed".format(hostname))

    if aggregated_result.failed:
        logger.error("Not all devices were successfully upgraded")
    else:
        logger.info("All devices successfully upgraded")

    return NornirJobResult(nrresult=aggregated_result)
