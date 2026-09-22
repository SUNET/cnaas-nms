import pytest

from cnaas_nms.devicehandler.interface_state import BOUNCE_CONFIRMED_REGEX, bounce_command


def test_bouncing_a_port_only_names_that_port():
    assert bounce_command("ge-0/0/23") == "request interface bounce ge-0/0/23"


def test_an_interval_keeps_the_port_down_long_enough_for_a_device_to_reboot():
    assert bounce_command("ge-0/0/23", interval=20) == "request interface bounce ge-0/0/23 interval 20"


def test_bouncing_poe_cuts_the_power_rather_than_the_link():
    assert bounce_command("ge-0/0/23", poe=True) == "request interface bounce poe ge-0/0/23"


def test_poe_and_an_interval_combine_into_one_command():
    assert bounce_command("ge-0/0/23", interval=30, poe=True) == "request interface bounce poe ge-0/0/23 interval 30"


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
    assert BOUNCE_CONFIRMED_REGEX.search(output)


@pytest.mark.parametrize("output", [NO_SUCH_INTERFACE, NO_POE_ON_INTERFACE, ""])
def test_a_refusal_is_not_mistaken_for_a_bounce(output):
    # Junos refuses in ordinary output rather than by failing, and its refusals
    # carry no marker word of their own, so anything short of a confirmation
    # has to count as "did not happen".
    assert not BOUNCE_CONFIRMED_REGEX.search(output)
