from cnaas_nms.confpush.nornir_helper import cnaas_init, inventory_selector
from cnaas_nms.tools.log import get_logger
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.confpush.nornir_helper import NornirJobResult
from cnaas_nms.db.session import sqla_session, redis_session
from cnaas_nms.db.device import DeviceType, Device
from cnaas_nms.scheduler.thread_data import set_thread_data

from nornir.plugins.functions.text import print_result
from nornir.plugins.tasks.networking import napalm_cli, napalm_get
from nornir.plugins.tasks.networking import netmiko_send_command
from nornir.core.task import MultiResult

from typing import Optional

import time


class FirmwareAlreadyActiveException(Exception):
    pass


def arista_pre_flight_check(task, job_id: Optional[str] = None) -> str:
    """
    NorNir task to do some basic checks before attempting to upgrade a switch.

    Args:
        task: NorNir task

    Returns:
        String, describing the result

    """
    set_thread_data(job_id)
    logger = get_logger()

    flash_diskspace = 'bash timeout 5 df /mnt/flash | awk \'{print $4}\''
    flash_cleanup = 'bash timeout 30 ls -t /mnt/flash/*.swi | tail -n +2 | grep -v `cut -d"/" -f2 /mnt/flash/boot-config` | xargs rm -f'

    # Get amount of free disk space
    res = task.run(napalm_cli, commands=[flash_diskspace])
    if not isinstance(res, MultiResult) or len(res.result.keys()) is not 1:
        raise Exception('Could not check free space')

    # Remove old firmware images if needed
    free_bytes = next(iter(res.result.values())).split('\n')[1]
    if int(free_bytes) < 2500000:
        logger.info('Cleaning up old firmware images on {}'.format(task.host.name))
        res = task.run(napalm_cli, commands=[flash_cleanup])
        print_result(res)
    else:
        logger.info('Enough free space ({}b), no cleanup'.format(free_bytes))

    return "Pre-flight check done."


def arista_post_flight_check(task, post_waittime: int, job_id: Optional[str] = None) -> str:
    """
    NorNir task to update device facts after a switch have been upgraded

    Args:
        task: NorNir task
        post_waittime: Time to wait before trying to gather facts

    Returns:
        String, describing the result

    """
    set_thread_data(job_id)
    logger = get_logger()
    time.sleep(int(post_waittime))
    logger.info('Post-flight check wait ({}s) complete, starting check for {}'.format(post_waittime, task.host.name))

    try:
        res = task.run(napalm_get, getters=["facts"])
        os_version = res[0].result['facts']['os_version']

        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.hostname == task.host.name).one()
            prev_os_version = dev.os_version
            dev.os_version = os_version
        if prev_os_version == os_version:
            logger.error("OS version did not change, activation failed on {}".format(task.host.name))
            raise Exception("OS version did not change, activation failed")
    except Exception as e:
        logger.exception("Could not update OS version on device {}: {}".format(task.host.name, str(e)))
        return 'Post-flight failed, could not update OS version: {}'.format(str(e))

    return "Post-flight, OS version updated from {} to {}.".format(prev_os_version,
                                                                   os_version)


def arista_firmware_download(task, filename: str, httpd_url: str,
                             job_id: Optional[str] = None) -> str:
    """
    NorNir task to download firmware image from the HTTP server.

    Args:
        task: NorNir task
        filename: Name of the file to download
        httpd_url: Base URL to the HTTP server

    Returns:
        String, describing the result

    """
    set_thread_data(job_id)
    logger = get_logger()

    url = httpd_url + '/' + filename

    try:
        with sqla_session() as session:
            dev: Device = session.query(Device).\
                filter(Device.hostname == task.host.name).one_or_none()
            device_type = dev.device_type

        if device_type == DeviceType.ACCESS:
            firmware_download_cmd = 'copy {} flash:'.format(url)
        else:
            firmware_download_cmd = 'copy {} vrf MGMT flash:'.format(url)

        res = task.run(netmiko_send_command, command_string='enable',
                       expect_string='.*#')
        print_result(res)

        res = task.run(netmiko_send_command,
                       command_string=firmware_download_cmd.replace("//", "/"),
                       delay_factor=30,
                       max_loops=200,
                       expect_string='.*Copy completed successfully.*')
        print_result(res)
    except Exception as e:
        logger.error('{} failed to download firmware: {}'.format(
            task.host.name, e))
        raise Exception('Failed to download firmware')

    return "Firmware download done."


def arista_firmware_activate(task, filename: str, job_id: Optional[str] = None) -> str:
    """
    NorNir task to modify the boot config for new firmwares.

    Args:
        task: NorNir task
        filename: Name of the new firmware image

    Returns:
        String, describing the result

    """
    set_thread_data(job_id)
    logger = get_logger()
    try:
        boot_file_cmd = 'boot system flash:{}'.format(filename)

        res = task.run(netmiko_send_command, command_string='enable',
                       expect_string='.*#')
        print_result(res)

        res = task.run(netmiko_send_command,
                       command_string='show boot-config | grep -o "\\w*{}\\w*"'.format(filename))
        print_result(res)
        if res.result == filename:
            raise FirmwareAlreadyActiveException(
                'Firmware already activated in boot-config on {}'.format(task.host.name))

        res = task.run(netmiko_send_command, command_string='conf t',
                       expect_string='.*config.*#')
        print_result(res)

        res = task.run(netmiko_send_command, command_string=boot_file_cmd)
        print_result(res)

        res = task.run(netmiko_send_command, command_string='end',
                       expect_string='.*#')
        print_result(res)

        res = task.run(netmiko_send_command,
                       command_string='show boot-config | grep -o "\\w*{}\\w*"'.format(filename))
        print_result(res)

        if not isinstance(res, MultiResult):
            raise Exception('Could not check boot-config on {}'.format(task.host.name))

        if res.result != filename:
            raise Exception('Firmware not activated properly on {}'.format(task.host.name))

    except Exception as e:
        logger.exception('Failed to activate firmware on {}: {}'.format(task.host.name, str(e)))
        raise Exception('Failed to activate firmware')

    return "Firmware activate done."


def arista_device_reboot(task, job_id: Optional[str] = None) -> str:
    """
    NorNir task to reboot a single device.

    Args:
        task: NorNir task.

    Returns:
        String, describing the result

    """
    set_thread_data(job_id)
    logger = get_logger()
    try:
        res = task.run(netmiko_send_command, command_string='enable',
                       expect_string='.*#')
        print_result(res)

        res = task.run(netmiko_send_command, command_string='write',
                       expect_string='.*#')
        print_result(res)

        res = task.run(netmiko_send_command, command_string='reload force',
                       max_loops=2,
                       expect_string='.*')
    except Exception as e:
        logger.exception('Failed to reboot switch {}: {}'.format(task.host.name,
                                                            str(e)))
        raise e

    return "Device reboot done."


def device_upgrade_task(task, job_id: str,
                        reboot: False, filename: str,
                        url: str,
                        download: Optional[bool] = False,
                        pre_flight: Optional[bool] = False,
                        post_flight: Optional[bool] = False,
                        post_waittime: Optional[int] = 0,
                        activate: Optional[bool] = False) -> NornirJobResult:

    # If pre-flight is selected, execute the pre-flight task which
    # will verify the amount of disk space and so on.
    set_thread_data(job_id)
    logger = get_logger()
    if pre_flight:
        logger.info('Running pre-flight check on {}'.format(task.host.name))
        try:
            res = task.run(task=arista_pre_flight_check, job_id=job_id)
        except Exception as e:
            logger.exception("Exception while doing pre-flight check: {}".
                             format(str(e)))
            raise Exception('Pre-flight check failed')
        else:
            if res.failed:
                logger.exception('Pre-flight check failed for: {}'.format(
                    ' '.join(res.failed_hosts.keys())))
                raise

    # If download is true, go ahead and download the firmware
    if download:
        # Download the firmware from the HTTP container.
        logger.info('Downloading firmware {} on {}'.format(filename,
                                                           task.host.name))
        try:
            res = task.run(task=arista_firmware_download, filename=filename,
                           httpd_url=url, job_id=job_id)
            print_result(res)
        except Exception as e:
            logger.exception('Exception while downloading firmware: {}'.format(
                str(e)))
            raise e

    # If download_only is false, continue to activate the newly downloaded
    # firmware and verify that it if present in the boot-config.
    already_active = False
    if activate:
        logger.info('Activating firmware {} on {}'.format(
            filename, task.host.name))
        try:
            res = task.run(task=arista_firmware_activate, filename=filename, job_id=job_id)
            print_result(res)
        except FirmwareAlreadyActiveException as e:
            already_active = True
            logger.debug("Firmware already active, skipping reboot and post_flight: {}".format(e))
        except Exception as e:
            logger.exception('Exception while activating firmware: {}'.format(
                str(e)))
            raise e

    # Reboot the device if needed, we will then lose the connection.
    if reboot and not already_active:
        logger.info('Rebooting {}'.format(task.host.name))
        try:
            res = task.run(task=arista_device_reboot, job_id=job_id)
        except Exception as e:
            pass

    # If post-flight is selected, execute the post-flight task which
    # will update device facts for the selected devices
    if post_flight and not already_active:
        logger.info('Running post-flight check on {}, delay start by {}s'.format(
            task.host.name, post_waittime))
        try:
            res = task.run(task=arista_post_flight_check, post_waittime=post_waittime, job_id=job_id)
        except Exception as e:
            logger.exception('Failed to run post-flight check: {}'.format(str(e)))
        else:
            if res.failed:
                logger.error('Post-flight check failed for: {}'.format(
                    ' '.join(res.failed_hosts.keys())))

    if job_id:
        with redis_session() as db:
            db.lpush('finished_devices_' + str(job_id), task.host.name)


@job_wrapper
def device_upgrade(download: Optional[bool] = False,
                   activate: Optional[bool] = False,
                   filename: Optional[bool] = None,
                   group: Optional[str] = None,
                   hostname: Optional[str] = None,
                   url: Optional[str] = None,
                   job_id: Optional[str] = None,
                   pre_flight: Optional[bool] = False,
                   post_flight: Optional[bool] = False,
                   post_waittime: Optional[int] = 600,
                   reboot: Optional[bool] = False,
                   scheduled_by: Optional[str] = None) -> NornirJobResult:

    logger = get_logger()
    nr = cnaas_init()
    if hostname:
        nr_filtered, dev_count, _ = inventory_selector(nr, hostname=hostname)
    elif group:
        nr_filtered, dev_count, _ = inventory_selector(nr, group=group)
    else:
        raise ValueError("Neither hostname nor group specified for device_upgrade")

    device_list = list(nr_filtered.inventory.hosts.keys())
    logger.info("Device(s) selected for firmware upgrade ({}): {}".format(
        dev_count, ", ".join(device_list)
    ))
    logger.info(f"Upgrade tasks selected: pre_flight = {pre_flight}, download = {download}, " +
                f"activate = {activate}, reboot = {reboot}, post_flight = {post_flight}")

    # Make sure we only upgrade Arista access switches
    for device in device_list:
        with sqla_session() as session:
            dev: Device = session.query(Device).\
                filter(Device.hostname == device).one_or_none()
            if not dev:
                raise Exception('Could not find device: {}'.format(device))
            if dev.platform != 'eos':
                raise Exception('Invalid device platform "{}" for device: {}'.format(
                    dev.platform, device))

    # Start tasks to take care of the upgrade
    try:
        nrresult = nr_filtered.run(task=device_upgrade_task,
                                   job_id=job_id,
                                   download=download,
                                   filename=filename,
                                   url=url,
                                   pre_flight=pre_flight,
                                   post_flight=post_flight,
                                   post_waittime=post_waittime,
                                   reboot=reboot,
                                   activate=activate)
    except Exception as e:
        logger.exception('Exception while upgrading devices: {}'.format(
            str(e)))
        return NornirJobResult(nrresult=nrresult)

    failed_hosts = list(nrresult.failed_hosts.keys())
    for hostname in failed_hosts:
        logger.error("Firmware upgrade of device '{}' failed".format(hostname))

    if nrresult.failed:
        logger.error("Not all devices were successfully upgraded")

    return NornirJobResult(nrresult=nrresult)
