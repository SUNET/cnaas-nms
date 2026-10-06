import pytest
from nornir.core import Nornir
from nornir.core.inventory import Defaults, Groups, Host, Hosts, Inventory
from nornir.core.task import Result
from nornir.plugins.runners import SerialRunner

from cnaas_nms.app_settings import app_settings
from cnaas_nms.devicehandler.interface_state import (
    bounce_command,
    bounce_confirmed,
    bounce_interfaces,
    bounce_task,
    junos_bounce_task,
)

# The two halves a bounce pushes, named here rather than imported so that
# renaming one in the source is caught instead of followed.
BOUNCE_DOWN = "bounce-down.j2"
BOUNCE_UP = "bounce-up.j2"

WORKING_DOWN = "interface {{ interfaces|join(',') }}\n  shutdown\n"
WORKING_UP = "interface {{ interfaces|join(',') }}\n  no shutdown\n"


@pytest.fixture
def template_repo(tmp_path, monkeypatch):
    """A template repository holding a usable pair of bounce templates for eos."""
    monkeypatch.setattr(app_settings, "TEMPLATES_LOCAL", str(tmp_path))
    platform_path = tmp_path / "eos"
    platform_path.mkdir()
    (platform_path / BOUNCE_DOWN).write_text(WORKING_DOWN)
    (platform_path / BOUNCE_UP).write_text(WORKING_UP)
    return platform_path


@pytest.fixture
def bounce(monkeypatch):
    """Bounce an interface on a switch whose config pushes are recorded.

    Returns a callable that runs the real bounce task and hands back the
    configs that reached the device, so a test can tell a refused bounce from
    one that pushed a half and then gave up.
    """
    pushed = []

    def fake_napalm_configure(task, configuration=None, **kwargs):
        pushed.append(configuration)
        return Result(host=task.host, changed=True, result="")

    monkeypatch.setattr("cnaas_nms.devicehandler.interface_state.napalm_configure", fake_napalm_configure)

    def run(interfaces=["Ethernet1"]):
        result = make_nornir().run(task=bounce_task, interfaces=interfaces)
        return result["sw1"], pushed

    return run


def make_nornir():
    """A Nornir holding one managed eos switch, as the bounce expects to find."""
    host = Host(name="sw1", platform="eos", data={"managed": True})
    inventory = Inventory(hosts=Hosts({"sw1": host}), groups=Groups(), defaults=Defaults())
    return Nornir(inventory=inventory, runner=SerialRunner())


@pytest.fixture
def bounce_device(bounce, monkeypatch):
    """Bounce through bounce_interfaces, the entry point the API calls.

    The checks needing a database and a reachable switch are replaced, leaving
    how a refusal inside the task reaches the caller.
    """
    monkeypatch.setattr("cnaas_nms.devicehandler.interface_state.pre_bounce_check", lambda *args: None)
    monkeypatch.setattr("cnaas_nms.devicehandler.interface_state.cnaas_init", make_nornir)
    return lambda interfaces=["Ethernet1"]: bounce_interfaces("sw1", interfaces)


def test_a_bounce_takes_the_interface_down_and_brings_it_back_up(template_repo, bounce):
    result, pushed = bounce(["Ethernet1"])

    assert not result.failed
    assert pushed == ["interface Ethernet1\n  shutdown\n", "interface Ethernet1\n  no shutdown\n"]


@pytest.mark.parametrize(
    "half,content",
    [
        (BOUNCE_UP, None),
        (BOUNCE_DOWN, None),
        (BOUNCE_UP, ""),
        (BOUNCE_UP, "{# nothing to do yet #}\n"),
        (BOUNCE_UP, "\n  \n"),
        (BOUNCE_UP, "{% for i in no_such_list %}interface {{ i }}\n{% endfor %}"),
        (BOUNCE_UP, "interface {% if %}\n"),
    ],
    ids=["up-missing", "down-missing", "up-empty", "up-comment-only", "up-blank", "up-loops-over-nothing", "up-broken"],
)
def test_a_bounce_that_cannot_produce_both_halves_pushes_neither(template_repo, bounce, half, content):
    # Pushing the down half and only then discovering there is no up half
    # leaves the interface disabled, which a later bounce cannot repair. So a
    # bounce that cannot produce both configs must not touch the device at all.
    if content is None:
        (template_repo / half).unlink()
    else:
        (template_repo / half).write_text(content)

    result, pushed = bounce(["Ethernet1"])

    assert result.failed
    assert pushed == []


def test_a_bounce_names_the_interface_it_was_asked_to_bounce(template_repo, bounce):
    # Every interface in the request has to reach the device, otherwise a
    # multi-interface bounce silently leaves some of them alone.
    _, pushed = bounce(["Ethernet1", "Ethernet2"])

    assert all("Ethernet1,Ethernet2" in config for config in pushed)


def test_a_refusal_names_the_template_and_platform_the_operator_has_to_fix(template_repo, bounce_device):
    # The operator fixes this in the template repository, so what comes back
    # out of bounce_interfaces has to say which file for which platform, not
    # just that some step of the bounce did not complete.
    (template_repo / BOUNCE_UP).write_text("")

    with pytest.raises(ValueError) as refusal:
        bounce_device(["Ethernet1"])

    assert BOUNCE_UP in str(refusal.value)
    assert "eos" in str(refusal.value)


def test_a_bounce_that_pushed_both_halves_reports_success(template_repo, bounce_device):
    assert bounce_device(["Ethernet1"]) is True


def test_bouncing_a_port_only_names_that_port():
    assert bounce_command("ge-0/0/23") == "request interface bounce ge-0/0/23"


def test_an_interval_keeps_the_port_down_long_enough_for_a_device_to_reboot():
    assert bounce_command("ge-0/0/23", interval=20) == "request interface bounce ge-0/0/23 interval 20"


def test_bouncing_poe_cuts_the_power_rather_than_the_link():
    assert bounce_command("ge-0/0/23", poe=True) == "request interface bounce poe ge-0/0/23"


@pytest.mark.parametrize("interval", [0, 31, -1])
def test_an_interval_the_switch_would_refuse_is_rejected_before_it_is_sent(interval):
    # Junos accepts 1 to 30 seconds; anything else is caught here rather than
    # ending up as an error message from the switch.
    with pytest.raises(ValueError):
        bounce_command("ge-0/0/23", interval=interval)


# What an EX4100 running Junos 24.4 actually answers, recorded on testcampus1.
BOUNCE_STARTED = "\nBounce operation on interface ge-0/0/16 started with interval 10 secs.\n"
POE_BOUNCE_STARTED = "\nPoE bounce request received for ge-0/0/16 with interval 5s\n"
NO_SUCH_INTERFACE = "\nPort bounce: IFD object ge-0/0/99 doesn't exist\n"
NO_POE_ON_INTERFACE = "\nPoE not supported on ge-0/0/99\n"


@pytest.mark.parametrize("output", [BOUNCE_STARTED, POE_BOUNCE_STARTED])
def test_the_switch_confirming_the_bounce_counts_as_done(output):
    assert bounce_confirmed(output)


@pytest.mark.parametrize(
    "output",
    [
        NO_SUCH_INTERFACE,
        NO_POE_ON_INTERFACE,
        "",
        "PoE bounce request rejected: port ge-0/0/16 is down",
        "Bounce operation on interface ge-0/0/16 failed",
    ],
)
def test_a_refusal_is_not_mistaken_for_a_bounce(output):
    # Junos refuses in ordinary output rather than by failing, and its refusals
    # carry no marker word of their own, so anything short of a confirmation
    # has to count as "did not happen" - including a refusal phrased with the
    # same words the confirmation uses.
    assert not bounce_confirmed(output)


# "show poe interface" in XML as NAPALM hands it back, recorded from EX switches
# running Junos 24.4: an access point drawing power, a PoE port with nothing
# drawing power, and a port the switch has no PoE for.
POE_DELIVERING = """
<rpc-reply xmlns:junos="http://xml.juniper.net/junos/24.4R2-S4.10/junos">
    <poe>
        <interface-information-detail>
            <interface-name-detail>mge-0/0/0</interface-name-detail>
            <interface-enabled-detail>Enabled</interface-enabled-detail>
            <interface-status-detail>ON</interface-status-detail>
            <interface-status-detail-extra>4P Port delivering 4P IEEE SSPD</interface-status-detail-extra>
            <interface-power-detail>11.4W</interface-power-detail>
        </interface-information-detail>
    </poe>
</rpc-reply>
"""
POE_IDLE = POE_DELIVERING.replace(">ON<", ">OFF<").replace("4P Port delivering 4P IEEE SSPD", "Detection In Progress")
POE_NOT_SUPPORTED = """
<rpc-reply>
    <poe>
        <interface-information-detail>
            <error>
                <parse/>
                <source-daemon>chassisd</source-daemon>
                <message>error: PoE is not supported on interface ae0</message>
            </error>
        </interface-information-detail>
    </poe>
</rpc-reply>
"""


@pytest.fixture
def bounce_port(monkeypatch):
    """Bounce ge-0/0/23 on a switch whose command replies are scripted.

    Returns a callable taking the reply to each command in turn, None for a
    command the switch refuses, which runs the real task and returns the
    commands the switch received and the task result.
    """

    def fake_napalm_cli(task, commands, **kwargs):
        reply = replies[len(sent)]
        sent.append(commands[0])
        if reply is None:
            raise ConnectionError("Unable to run {} on {}".format(commands[0], task.host.name))
        return Result(host=task.host, result={commands[0]: reply})

    sent: list = []
    replies: list = []
    monkeypatch.setattr("cnaas_nms.devicehandler.interface_state.napalm_cli", fake_napalm_cli)

    def run(command_replies, ifname="ge-0/0/23"):
        replies.extend(command_replies)
        host = Host(name="junosaccess", platform="junos")
        inventory = Inventory(hosts=Hosts({"junosaccess": host}), groups=Groups(), defaults=Defaults())
        nornir = Nornir(inventory=inventory, runner=SerialRunner())
        result = nornir.run(task=junos_bounce_task, interfaces=[ifname], interval=20)["junosaccess"]
        return sent, result

    return run


def test_a_port_powering_its_device_is_power_cycled(bounce_port):
    # Bouncing only the link would leave an access point running on PoE, while
    # the point of a bounce is to restart it.
    sent, result = bounce_port([POE_DELIVERING, POE_BOUNCE_STARTED])

    assert not result.failed
    assert sent[-1] == "request interface bounce poe ge-0/0/23 interval 20"


@pytest.mark.parametrize("poe_status", [POE_IDLE, POE_NOT_SUPPORTED, None])
def test_a_port_not_powering_a_device_has_its_link_bounced(bounce_port, poe_status):
    # The switch refuses a PoE bounce where there is no PoE, so a port without
    # a powered device, or on a switch that cannot say, still gets bounced.
    sent, result = bounce_port([poe_status, BOUNCE_STARTED])

    assert not result.failed
    assert sent[-1] == "request interface bounce ge-0/0/23 interval 20"


@pytest.mark.parametrize("ifname", ["ge-0/0/23 | match secret", "ge-0/0/23\nshow configuration", "ge-0/0/23;id"])
def test_a_name_that_appends_a_second_command_never_reaches_the_switch(bounce_port, ifname):
    # The interface name is interpolated into CLI commands, so a name that is
    # not an interface name is refused before anything is sent.
    sent, result = bounce_port([POE_DELIVERING, POE_BOUNCE_STARTED], ifname=ifname)

    assert result.failed
    assert sent == []
