import logging

from cnaas_nms.app_settings import app_settings
from cnaas_nms.tools.log import get_logger


def test_get_logger_default_level():
    """get_logger() should apply the configured LOG_LEVEL the first time it sets up a logger."""
    logger = logging.getLogger("cnaas-nms")
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)

    logger = get_logger()

    assert logger.name == "cnaas-nms"
    assert logger.level == logging.getLevelName(app_settings.LOG_LEVEL)


def test_get_logger_does_not_reset_level_on_repeated_calls():
    """Regression test: get_logger() must not clobber a level set after initial configuration
    (e.g. by caplog.at_level or other runtime overrides) on subsequent calls."""
    logger = logging.getLogger("cnaas-nms")
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)

    get_logger()  # first call configures handlers + default level
    logger.setLevel(logging.DEBUG)  # simulate an external override

    get_logger()  # second call must not reset the level back to the default

    assert logger.level == logging.DEBUG
