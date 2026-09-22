import pytest
from nornir.core import Nornir
from nornir.core.inventory import Defaults, Groups, Host, Hosts, Inventory
from nornir.core.task import Result
from nornir.plugins.runners import SerialRunner

from cnaas_nms.app_settings import app_settings
from cnaas_nms.devicehandler.interface_state import bounce_task

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
        host = Host(name="sw1", platform="eos")
        inventory = Inventory(hosts=Hosts({"sw1": host}), groups=Groups(), defaults=Defaults())
        nornir = Nornir(inventory=inventory, runner=SerialRunner())
        result = nornir.run(task=bounce_task, interfaces=interfaces)
        return result["sw1"], pushed

    return run


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


def test_a_refusal_names_the_template_and_platform_the_operator_has_to_fix(template_repo, bounce):
    # The operator fixes this in the template repository, so the error has to
    # say which file for which platform, not just that the bounce failed.
    (template_repo / BOUNCE_UP).write_text("")

    result, _ = bounce(["Ethernet1"])

    assert BOUNCE_UP in str(result.exception)
    assert "eos" in str(result.exception)
