from typing import List, Optional

from nornir_jinja2.plugins.tasks import template_file
from nornir_napalm.plugins.tasks import napalm_configure, napalm_get

from cnaas_nms.app_settings import app_settings
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.db.session import sqla_session
from cnaas_nms.devicehandler.nornir_helper import cnaas_init, get_jinja_env


def get_interface_states(hostname) -> dict:
    nr = cnaas_init()
    nr_filtered = nr.filter(name=hostname).filter(managed=True)
    if len(nr_filtered.inventory) != 1:
        raise ValueError(f"Hostname {hostname} not found in inventory")
    nrresult = nr_filtered.run(task=napalm_get, getters=["interfaces"])
    if not len(nrresult) == 1:
        raise Exception(f"Could not get interfaces for {hostname}: no Nornir result")
    if nrresult.failed or nrresult[hostname].failed:
        raise Exception(
            "Could not get interfaces for {}, NAPALM failed: {}".format(hostname, nrresult[hostname].exception)
        )
    return nrresult[hostname][0].result["interfaces"]


def pre_bounce_check(hostname: str, interfaces: List[str]):
    # Check1: Database state
    with sqla_session() as session:  # type: ignore
        dev: Optional[Device] = session.query(Device).filter(Device.hostname == hostname).one_or_none()
        if not dev:
            raise ValueError(f"Hostname {hostname} not found in database")
        if dev.device_type != DeviceType.ACCESS or dev.state != DeviceState.MANAGED:
            raise ValueError(f"Hostname {hostname} is not of type ACCESS or not in state MANAGED")
        db_intfs: List = (
            session.query(Interface)
            .filter(Interface.device == dev)
            .filter(Interface.configtype == InterfaceConfigType.ACCESS_UPLINK)
            .all()
        )
        uplink_intf_names = [x.name for x in db_intfs]
        for interface in interfaces:
            if interface in uplink_intf_names:
                raise ValueError("Can't bounce UPLINK port {} for device {}".format(interface, hostname))
    # Check2: Current interface state on device
    intf_states = get_interface_states(hostname)
    for interface in interfaces:
        if interface not in intf_states.keys():
            raise ValueError("Specified interface {} not found on device {}".format(interface, hostname))
        if "is_enabled" not in intf_states[interface] or not intf_states[interface]["is_enabled"]:
            raise ValueError("Specified interface {} on device {} is not enabled".format(interface, hostname))
    # Check3: config hash?


BOUNCE_HALVES = ("down", "up")


def bounce_task(task, interfaces: List[str]):
    """Take the interfaces down and bring them back up with two config pushes.

    Both halves are rendered before either is pushed. A bounce that pushes the
    down config and only then finds it cannot produce an up config leaves the
    interface disabled, with a config hash that no longer matches, so
    device_syncto refuses the device afterwards and a second bounce cannot
    repair it either because pre_bounce_check requires an enabled interface.
    """
    template_vars = {"interfaces": interfaces}
    local_repo_path = app_settings.TEMPLATES_LOCAL
    jinja_env = get_jinja_env(f"{local_repo_path}/{task.host.platform}")
    configs = []
    for half in BOUNCE_HALVES:
        r = task.run(
            task=template_file,
            name="Generate port bounce {} config".format(half),
            template="bounce-{}.j2".format(half),
            jinja_env=jinja_env,
            **template_vars,
        )
        if not r.result.strip():
            raise ValueError(
                "Template bounce-{}.j2 for platform {} renders an empty config, so bouncing {} "
                "would leave the interface in the state the other half put it in".format(
                    half, task.host.platform, ", ".join(interfaces)
                )
            )
        configs.append(r.result)
    for half, config in zip(BOUNCE_HALVES, configs):
        task.host["config"] = config
        task.run(
            task=napalm_configure,
            name="Port bounce {}".format(half),
            replace=False,
            configuration=task.host["config"],
        )


def bounce_interfaces(hostname: str, interfaces: List[str]) -> bool:
    """Returns true if the device changed config down and then up.
    Returns false if config did not change, and raises Exception if an
    error was encountered."""
    pre_bounce_check(hostname, interfaces)
    nr = cnaas_init()
    nr_filtered = nr.filter(name=hostname).filter(managed=True)
    if len(nr_filtered.inventory) != 1:
        raise ValueError(f"Hostname {hostname} not found in inventory")
    nrresult = nr_filtered.run(task=bounce_task, interfaces=interfaces)
    if nrresult.failed or nrresult[hostname].failed:
        # A template that cannot render names the file the operator has to fix,
        # which is worth more than the step count that would otherwise report it
        exception = nrresult[hostname].exception
        if isinstance(exception, ValueError):
            raise exception
        raise Exception("Could not bounce interfaces on {}: {}".format(hostname, exception))
    # 5 results: bounce_task, gen down config, gen up config, push down config, push up config
    if not len(nrresult[hostname]) == 5:
        raise Exception("Not all steps of port bounce completed")
    if nrresult[hostname][3].changed and nrresult[hostname][4].changed:
        return True
    else:
        return False
