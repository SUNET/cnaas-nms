import cnaas_nms.confpush.nornir_helper

from cnaas_nms.tools.log import get_logger
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.confpush.nornir_helper import NornirJobResult
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.device import DeviceType, Device

from nornir.plugins.functions.text import print_result
from nornir.plugins.tasks.networking import netmiko_send_command


logger = get_logger()


def device_erase_task(task, hostname: str) -> str:
    try:
        res = task.run(netmiko_send_command, command_string='enable',
                       expect_string='.*#',
                       name='Enable')
        print_result(res)

        res = task.run(netmiko_send_command,
                       command_string='write erase now',
                       expect_string='.*#',
                       name='Write rase')
        print_result(res)
    except Exception as e:
        logger.info('Failed to factory default device {}, reason: {}'.format(
            task.host.name, e))
        raise Exception('Factory default device')

    try:
        res = task.run(netmiko_send_command, command_string='reload force',
                       max_loops=2,
                       expect_string='.*')
        print_result(res)
    except Exception as e:
        pass

    return "Device factory defaulted"


@job_wrapper
def device_erase(device_id: int = None, job_id: int = None) -> NornirJobResult:

    with sqla_session() as session:
        dev: Device = session.query(Device).filter(Device.id ==
                                                   device_id).one_or_none()
        if dev:
            hostname = dev.hostname
            device_type = dev.device_type
        else:
            raise Exception('Could not find a device with ID {}'.format(
                device_id))

    if device_type != DeviceType.ACCESS:
        raise Exception('Can only do factory default on access')

    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    nr_filtered = nr.filter(name=hostname).filter(managed=True)

    device_list = list(nr_filtered.inventory.hosts.keys())
    logger.info("Device selected: {}".format(
        device_list
    ))

    try:
        nrresult = nr_filtered.run(task=device_erase_task,
                                   hostname=hostname)
        print_result(nrresult)
    except Exception as e:
        logger.exception('Exception while erasing device: {}'.format(
            str(e)))
        return NornirJobResult(nrresult=nrresult)

    failed_hosts = list(nrresult.failed_hosts.keys())
    for hostname in failed_hosts:
        logger.error("Failed to factory default device '{}' failed".format(
            hostname))

    if nrresult.failed:
        logger.error("Factory default failed")

    if failed_hosts == []:
        with sqla_session() as session:
            dev: Device = session.query(Device).filter(Device.id ==
                                                       device_id).one_or_none()
            session.delete(dev)
            session.commit()

    return NornirJobResult(nrresult=nrresult)
