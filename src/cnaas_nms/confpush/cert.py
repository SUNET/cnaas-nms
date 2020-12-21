import os
from typing import Optional

from nornir_netmiko import netmiko_file_transfer, netmiko_send_command

from cnaas_nms.scheduler.thread_data import set_thread_data
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.get_apidata import get_apidata


class CopyError(Exception):
    pass


def arista_copy_cert(task, job_id: Optional[str] = None) -> str:
    set_thread_data(job_id)
    logger = get_logger()
    apidata = get_apidata()

    try:
        key_path = os.path.join(apidata['certpath'], "{}.key".format(task.host.name))
        crt_path = os.path.join(apidata['certpath'], "{}.crt".format(task.host.name))
    except KeyError:
        raise Exception("No certpath found in api.yml settings")
    except Exception as e:
        raise Exception("Unable to find path to cert {} for device".format(e, task.host.name))

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
        overwrite_file=True
    )
    if res_key.failed:
        logger.exception(res_key.exception)

    res_crt = task.run(
        netmiko_file_transfer,
        source_file=crt_path,
        dest_file="cnaasnms.crt",
        file_system="/mnt/flash",
        overwrite_file=True
    )
    if res_crt.failed:
        logger.exception(res_crt.exception)

    if res_key.failed or res_crt.failed:
        raise CopyError("Unable to copy cert file to device: {}".format(task.host.name))

    certstore_commands = [
        "copy flash:cnaasnms.crt certificate:",
        "copy flash:cnaasnms.key sslkey:",
        "delete flash:cnaasnms.key",
        "delete flash:cnaasnms.crt"
    ]
    for cmd in certstore_commands:
        res_certstore = task.run(
            netmiko_send_command,
            command_string=cmd,
            enable=True
        )
        if res_certstore.failed:
            raise CopyError("Unable to copy cert into certstore on device: {}".
                            format(task.host.name))

    return "Cert copy successful"
