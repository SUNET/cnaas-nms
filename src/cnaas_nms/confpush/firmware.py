import cnaas_nms.confpush.nornir_helper

from cnaas_nms.tools.log import get_logger
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.confpush.nornir_helper import NornirJobResult
from cnaas_nms.db.session import sqla_session, redis_session
from cnaas_nms.db.device import DeviceType, Device

from nornir.plugins.functions.text import print_result
from nornir.plugins.tasks.networking import napalm_cli, napalm_configure, napalm_get
from nornir.plugins.tasks.networking import netmiko_send_command
from nornir.core.filter import F
from nornir.core.task import MultiResult

from napalm.base.exceptions import CommandErrorException

from typing import Optional


logger = get_logger()


def arista_pre_flight_check(task):
    """
    NorNir task to do some basic checks before attempting to upgrade a switch.

    Args:
        task: NorNir task

    Returns:
        Nope, nothing.

    """
    logger.info("Pre-flight check for {}".format(task.host.name))

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


def arista_firmware_download(task, filename: str, httpd_url: str) -> None:
    """
    NorNir task to download firmware image from the HTTP server.

    Args:
        task: NorNir task
        filename: Name of the file to download
        httpd_url: Base URL to the HTTP server

    Returns:
        Nothing.

    """
    logger.info('Downloading firmware for {}'.format(task.host.name))

    try:
        with sqla_session() as session:
            dev: Device = session.query(Device).\
                filter(Device.hostname == task.host.name).one_or_none()
            device_type = dev.device_type

        if device_type == 'ACCESS':
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
        logger.info('{} failed to download firmware: {}'.format(
            task.host.name, e))
        raise Exception('Failed to download firmware')

    return "Firmware download done."


def arista_firmware_activate(task, filename: str) -> None:
    """
    NorNir task to modify the boot config for new firmwares.

    Args:
        task: NorNir task
        filename: Name of the new firmware image

    Returns:
        Nope.

    """
    try:
        boot_file_cmd = 'boot system flash:{}'.format(filename)

        res = task.run(netmiko_send_command, command_string='enable',
                       expect_string='.*#')
        print_result(res)

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
        logger.exception('Failed to activate firmware: {}'.format(str(e)))
        raise Exception('Failed to activate firmware')

    return "Firmware activate done."


def arista_device_reboot(task) -> None:
    """
    NorNir task to reboot a single device.

    Args:
        task: NorNir task.

    Returns:
        Nothing.

    """
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


def device_upgrade_task(task, job_id: str, reboot: False, filename: str,
                        url: str,
                        download: Optional[bool] = False,
                        pre_flight: Optional[bool] = False,
                        activate: Optional[bool] = False) -> NornirJobResult:

    # If pre-flight is selected, execute the pre-flight task which
    # will verify the amount of disk space and so on.
    if pre_flight:
        logger.info('Running pre-flight check on {}'.format(task.host.name))
        try:
            res = task.run(task=arista_pre_flight_check)
            print_result(res)
        except Exception as e:
            logger.exception("Exception while doing pre-flight check: {}".
                             format(str(e)))
            raise Exception('Pre-flight check failed')
        else:
            if res.failed:
                logger.exception('Pre-flight check failed for: {}'.format(
                    ' '.join(res.failed_hosts.keys())))
                raise e

    # If download is true, go ahead and download the firmware
    if download:
        # Download the firmware from the HTTP container.
        logger.info('Downloading firmware {} on {}'.format(filename,
                                                           task.host.name))
        try:
            res = task.run(task=arista_firmware_download, filename=filename,
                           httpd_url=url)
            print_result(res)
        except Exception as e:
            logger.exception('Exception while downloading firmware: {}'.format(
                str(e)))
            raise e

    # If download_only is false, continue to activate the newly downloaded
    # firmware and verify that it if present in the boot-config.
    if activate:
        logger.info('Activating firmware {} on {}'.format(
            filename, task.host.name))
        try:
            res = task.run(task=arista_firmware_activate, filename=filename)
            print_result(res)
        except Exception as e:
            logger.exception('Exception while activating firmware: {}'.format(
                str(e)))
            raise e

    # Reboot the device if needed, we will then lose the connection.
    if reboot:
        logger.info('Rebooting {}'.format(task.host.name))
        try:
            res = task.run(task=arista_device_reboot)
        except Exception as e:
            pass

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
                   reboot: Optional[bool] = False,
                   scheduled_by: Optional[str] = None) -> NornirJobResult:

    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    if hostname:
        nr_filtered = nr.filter(name=hostname).filter(managed=True)
    elif group:
        nr_filtered = nr.filter(F(groups__contains=group))
    else:
        nr_filtered = nr.filter(synchronized=False).filter(managed=True)

    device_list = list(nr_filtered.inventory.hosts.keys())
    logger.info("Device(s) selected for firmware upgrade: {}".format(
        device_list
    ))

    # Make sure we only upgrade Arista access switches
    for device in device_list:
        with sqla_session() as session:
            dev: Device = session.query(Device).\
                filter(Device.hostname == device).one_or_none()
            if not dev or dev.device_type != DeviceType.ACCESS:
                raise Exception('Invalid device type: {}'.format(device))
            if not dev or dev.platform != 'eos':
                raise Exception('Invalid device platform: {}'.format(device))

    # Start tasks to take care of the upgrade
    try:
        nrresult = nr_filtered.run(task=device_upgrade_task, job_id=job_id,
                                   download=download,
                                   filename=filename,
                                   url=url,
                                   pre_flight=pre_flight,
                                   reboot=reboot,
                                   activate=activate)
        print_result(nrresult)
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
