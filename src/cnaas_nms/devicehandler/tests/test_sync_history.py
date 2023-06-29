from cnaas_nms.devicehandler.sync_history import add_sync_event, get_sync_events


def test_set_sync_history(postgresql, redis):
    add_sync_event("eosdist1", "refresh_settings", "indy@sunet.se", 123)


def test_get_sync_history(postgresql, redis):
    print(get_sync_events("eosdist1"))
