from nornir_netmiko.tasks import netmiko_send_command
from nornir_utils.plugins.functions import print_result

import cnaas_nms.confpush.nornir_helper
from cnaas_nms.confpush.nornir_helper import NornirJobResult
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.session import sqla_session
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.tools.log import get_logger

logger = get_logger()


def device_erase_task(task, hostname: str) -> str:
    try:
        res = task.run(netmiko_send_command, command_string="enable", expect_string=".*#", name="Enable")

        res = task.run(netmiko_send_command, command_string="write erase now", expect_string=".*#", name="Write rase")
        print_result(res)
    except Exception as e:
        logger.info("Failed to factory default device {}, reason: {}".format(task.host.name, e))
        raise Exception("Factory default device")

    # Remove cnaas device certificates if they are found
    try:
        task.run(
            netmiko_send_command,
            command_string="delete certificate:cnaasnms.crt",
            expect_string=".*#",
            name="Remove device certificate",
        )
        task.run(
            netmiko_send_command,
            command_string="delete sslkey:cnaasnms.key",
            expect_string=".*#",
            name="Remove device key",
        )
    except Exception:  # noqa: S110
        pass

    try:
        res = task.run(netmiko_send_command, command_string="reload force", max_loops=2, expect_string=".*")
        print_result(res)
    except Exception:  # noqa: S110
        pass

    return "Device factory defaulted"


@job_wrapper
def device_erase(device_id: int = None, job_id: int = None) -> NornirJobResult:

    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.id == device_id).one_or_none()
        if dev:
            hostname = dev.hostname
            device_type = dev.device_type
            device_state = dev.state
        else:
            raise Exception("Could not find a device with ID {}".format(device_id))

    if device_type != DeviceType.ACCESS:
        raise Exception("Can only do factory default on access")

    if device_state not in [DeviceState.MANAGED, DeviceState.UNMANAGED]:
        raise Exception("Can only do factory default on MANAGED or UNMANAGED devices")

    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname)

    device_list = list(nr_filtered.inventory.hosts.keys())
    logger.info("Device selected: {}".format(device_list))

    try:
        nrresult = nr_filtered.run(task=device_erase_task, hostname=hostname)
        print_result(nrresult)
    except Exception as e:
        logger.exception("Exception while erasing device: {}".format(str(e)))
        return NornirJobResult(nrresult=nrresult)

    failed_hosts = list(nrresult.failed_hosts.keys())
    for hostname in failed_hosts:
        logger.error("Failed to factory default device '{}' failed".format(hostname))

    if nrresult.failed:
        logger.error("Factory default failed")

    if failed_hosts == []:
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.id == device_id).one_or_none()
            session.delete(dev)
            session.commit()

    return NornirJobResult(nrresult=nrresult)
