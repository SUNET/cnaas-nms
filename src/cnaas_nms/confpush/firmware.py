import cnaas_nms.confpush.nornir_helper

from cnaas_nms.tools.log import get_logger
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.confpush.nornir_helper import NornirJobResult
from cnaas_nms.db.session import sqla_session, redis_session
from cnaas_nms.db.device import DeviceType, Device
from nornir.plugins.functions.text import print_result
from nornir.plugins.tasks.networking import napalm_get
from nornir.plugins.tasks.networking import napalm_cli, napalm_configure
from nornir.core.filter import F
from nornir.core.task import MultiResult

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
    flash_cleanup = 'ls -t /mnt/flash | tail -n +2 | xargs rm'

    # Get amount of free disk space
    res = task.run(napalm_cli, commands=[flash_diskspace])
    if not isinstance(res, MultiResult) or len(res.result.keys()) is not 1:
        raise Exception('Could not check free space')

    # Remove old firmware images if needed
    free_bytes = next(iter(res.result.values())).split('\n')[1]
    if int(free_bytes) < 1500000:
        logger.info('Cleaning up old firmware images on {}'.format(task.host.name))
        res = task.run(napalm_cli, commands=[flash_cleanup])
        print_result(res)
    else:
        logger.info('Enough free space ({}b), no cleanup'.format(free_bytes))


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

    firmware_download_cmd = 'copy {}/{} flash:'.format(httpd_url, filename)

    try:
        res = task.run(napalm_cli,
                       commands=[firmware_download_cmd.replace("//", "/")])

        print_result(res)
    except Exception as e:
        logger.info('{} failed to download firmware: {}'.format(
            task.host.name, e))


def arista_firmware_activate(task, filename: str) -> None:
    """
    NorNir task to modify the boot config for new firmwares.

    Args:
        task: NorNir task
        filename: Name of the new firmware image

    Returns:
        Nope.

    """
    boot_file_cmd = 'boot system flash:{}'.format(filename)

    res = task.run(napalm_configure, dry_run=False,
                   configuration=boot_file_cmd,
                   replace=False)

    print_result(res)

    res = task.run(napalm_cli,
                   commands=['show boot-config | grep -o "\\w*{}\\w*"'.format(
                       filename)])

    print_result(res)

    if not isinstance(res, MultiResult) or len(res.result.keys()) is not 1:
        raise('Could not check boot-config')

    if next(iter(res.result.values())).rstrip() != filename:
        raise Exception('Could not acticate new firmware')

    logger.info('New firmware activated')


def arista_device_reboot(task) -> None:
    """
    NorNir task to reboot a single device.

    Args:
        task: NorNir task.

    Returns:
        Nothing.

    """
    res = task.run(napalm_cli, commands=['write', 'reload force'])

    print_result(res)


def device_upgrade_task(task, job_id: str, reboot: False, filename: str,
                        url: str,
                        download_only: Optional[bool] = True,
                        pre_flight: Optional[bool] = True) -> NornirJobResult:

    # If pre-flight is selected, execute the pre-flight task which
    # will verify the amount of disk space and so on.
    if pre_flight is not None:
        try:
            res = task.run(task=arista_pre_flight_check)
            print_result(res)
        except Exception as e:
            logger.exception("Exception while doing pre-flight check: {}".format(str(e)))
            raise e
        else:
            if res.failed:
                raise Exception('Pre-flight check failed for: {}'.format(
                    ' '.join(res.failed_hosts.keys())))
    else:
        logger.info('Skepping pre-flight check')

    # Download the firmware from the HTTP container.
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
    if download_only is False:
        try:
            res = task.run(task=arista_firmware_activate, filename=filename)
            print_result(res)
        except Exception as e:
            logger.exception('Exception while activating firmware: {}'.format(
                str(e)))
            raise e
    else:
        logger.info('Will not activate new firmware')

    # Reboot the device if needed, we will then lose the connection.
    if reboot:
        try:
            res = task.run(task=arista_device_reboot)
        except Exception as e:
            logger.exceptio('Devices rebooted, connection lost. All good.')
    else:
        logger.info('Will not reboot devices')

    if job_id:
        with redis_session() as db:
            db.lpush('finished_devices_' + str(job_id), task.host.name)
            logger.info('finished_devices_' + str(job_id))


@job_wrapper
def device_upgrade(download_only: Optional[bool] = True,
                   filename: Optional[bool] = None,
                   group: Optional[str] = None,
                   hostname: Optional[str] = None,
                   url: Optional[str] = None,
                   job_id: Optional[str] = None,
                   pre_flight: Optional[bool] = True,
                   reboot: Optional[bool] = False) -> NornirJobResult:

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

    # Make sure we only upgrade access switches
    for device in device_list:
        with sqla_session() as session:
            dev: Device = session.query(Device).\
                filter(Device.hostname == device).one_or_none()
            if not dev or dev.device_type != DeviceType.ACCESS:
                raise Exception('Invalid device type: {}'.format(device))

    # Start tasks to take care of the upgrade
    try:
        nrresult = nr_filtered.run(task=device_upgrade_task, job_id=job_id,
                                   download_only=download_only,
                                   filename=filename,
                                   url=url,
                                   pre_flight=pre_flight,
                                   reboot=reboot)
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
