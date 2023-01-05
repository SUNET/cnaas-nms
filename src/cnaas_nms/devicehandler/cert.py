import os
from typing import Optional

from nornir_netmiko import netmiko_file_transfer, netmiko_send_command

from cnaas_nms.app_settings import api_settings
from cnaas_nms.db.device import Device
from cnaas_nms.db.session import sqla_session
from cnaas_nms.devicehandler.nornir_helper import NornirJobResult, cnaas_init, inventory_selector
from cnaas_nms.scheduler.thread_data import set_thread_data
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.pki import generate_device_cert


class CopyError(Exception):
    pass


def arista_copy_cert(task, job_id: Optional[str] = None) -> str:
    set_thread_data(job_id)
    logger = get_logger()

    try:
        key_path = os.path.join(api_settings.CERTPATH, "{}.key".format(task.host.name))
        crt_path = os.path.join(api_settings.CERTPATH, "{}.crt".format(task.host.name))
    except KeyError:
        raise Exception("No certpath found in api.yml settings")
    except Exception as e:
        raise Exception("Unable to find path to cert {} for device {}".format(e, task.host.name))

    if not os.path.isfile(key_path):
        raise Exception("Key file {} not found".format(key_path))
    if not os.path.isfile(crt_path):
        raise Exception("Cert file {} not found".format(crt_path))

    net_connect = task.host.get_connection("netmiko", task.nornir.config)
    net_connect.fast_cli = False

    res_key = task.run(
        netmiko_file_transfer,
        source_file=key_path,
        dest_file="cnaasnms.key",
        file_system="/mnt/flash",
        overwrite_file=True,
    )
    if res_key.failed:
        logger.exception(res_key.exception)

    res_crt = task.run(
        netmiko_file_transfer,
        source_file=crt_path,
        dest_file="cnaasnms.crt",
        file_system="/mnt/flash",
        overwrite_file=True,
    )
    if res_crt.failed:
        logger.exception(res_crt.exception)

    if res_key.failed or res_crt.failed:
        raise CopyError("Unable to copy cert file to device: {}".format(task.host.name))
    else:
        logger.debug("Certificate successfully copied to device: {}".format(task.host.name))

    certstore_commands = [
        "copy flash:cnaasnms.crt certificate:",
        "copy flash:cnaasnms.key sslkey:",
        "delete flash:cnaasnms.key",
        "delete flash:cnaasnms.crt",
    ]
    for cmd in certstore_commands:
        res_certstore = task.run(netmiko_send_command, command_string=cmd, enable=True)
        if res_certstore.failed:
            logger.error(
                "Unable to copy cert into certstore on device: {}, command '{}' failed".format(task.host.name, cmd)
            )
            raise CopyError("Unable to copy cert into certstore on device: {}".format(task.host.name))

    logger.debug("Certificate successfully copied to certstore on device: {}".format(task.host.name))
    return "Cert copy successful"


def renew_cert_task(task, job_id: str) -> str:
    set_thread_data(job_id)
    logger = get_logger()

    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.hostname == task.host.name).one_or_none()
        ip = dev.management_ip
        if not ip:
            raise Exception("Device {} has no management_ip".format(task.host.name))

    try:
        generate_device_cert(task.host.name, ipv4_address=ip)
    except Exception as e:
        raise Exception("Could not generate certificate for device {}: {}".format(task.host.name, e))

    if task.host.platform == "eos":
        try:
            task.run(task=arista_copy_cert, job_id=job_id)
        except Exception as e:
            logger.exception("Exception while copying certificates: {}".format(str(e)))
            raise e
    else:
        raise ValueError("Unsupported platform: {}".format(task.host.platform))

    return "Certificate renew success for device {}".format(task.host.name)


@job_wrapper
def renew_cert(
    hostname: Optional[str] = None,
    group: Optional[str] = None,
    job_id: Optional[str] = None,
    scheduled_by: Optional[str] = None,
) -> NornirJobResult:

    logger = get_logger()
    nr = cnaas_init()
    if hostname:
        nr_filtered, dev_count, _ = inventory_selector(nr, hostname=hostname)
    elif group:
        nr_filtered, dev_count, _ = inventory_selector(nr, group=group)
    else:
        raise ValueError("Neither hostname nor group specified for renew_cert")

    device_list = list(nr_filtered.inventory.hosts.keys())
    logger.info("Device(s) selected for renew certificate ({}): {}".format(dev_count, ", ".join(device_list)))

    supported_platforms = ["eos"]
    # Make sure we only attempt supported devices
    for device in device_list:
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.hostname == device).one_or_none()
            if not dev:
                raise Exception("Could not find device: {}".format(device))
            if dev.platform not in supported_platforms:
                raise Exception('Unsupported device platform "{}" for device: {}'.format(dev.platform, device))

    try:
        nrresult = nr_filtered.run(task=renew_cert_task, job_id=job_id)
    except Exception as e:
        logger.exception("Exception while renewing certificates: {}".format(str(e)))
        return NornirJobResult(nrresult=nrresult)

    failed_hosts = list(nrresult.failed_hosts.keys())
    for hostname in failed_hosts:
        logger.error("Certificate renew on device '{}' failed".format(hostname))

    if nrresult.failed:
        logger.error("Not all devices got new certificates")

    return NornirJobResult(nrresult=nrresult)
