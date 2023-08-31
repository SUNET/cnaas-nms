from cnaas_nms.devicehandler.sync_history import add_sync_event, get_sync_events, remove_sync_events


def test_set_sync_history(redis):
    add_sync_event("eosdist1", "refresh_settings", "unittest", 123)
    add_sync_event("eosdist1", "refresh_settings", "unittest", 124)
    add_sync_event("eosdist1", "ztp", "unittest")


def test_get_sync_history(redis):
    print(get_sync_events("eosdist1"))


def test_remove_sync_history(redis):
    remove_sync_events("eosdist1")
    print(get_sync_events("eosdist1"))
