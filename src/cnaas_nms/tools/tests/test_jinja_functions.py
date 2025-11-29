import unittest

from jinja2 import Environment
from jinja2.exceptions import TemplateError

from cnaas_nms.tools.jinja_functions import (
    log,
    raise_helper,
)


class FailTests(unittest.TestCase):
    def test_fail_exception(self):
        with self.assertRaises(TemplateError) as cm:
            raise_helper("this raises TemplateError")
        assert cm.exception.message == "this raises TemplateError"

    def test_fail_in_jinja(self):
        env = Environment(autoescape=True)
        env.globals["raise"] = raise_helper

        template = env.from_string('{{ raise("some exception") }}')

        with self.assertRaises(TemplateError) as cm:
            template.render()
        assert cm.exception.message == "some exception"


class LogTests(unittest.TestCase):
    def test_log_filter(self):
        with self.assertLogs("cnaas-nms", "INFO") as cm:
            log("this is a info-log")
            log("this is also a info-log", "info")
        assert len(cm.records) == 2
        assert cm.records[0].msg == "this is a info-log"
        assert cm.records[0].levelname == "INFO"

        with self.assertLogs("cnaas-nms", "WARNING") as cm:
            log("this is a warning-log", "WARNING")
        assert len(cm.records) == 1
        assert cm.records[0].msg == "this is a warning-log"
        assert cm.records[0].levelname == "WARNING"

        with self.assertLogs("cnaas-nms", "CRITICAL") as cm:
            log("this is a critical-log", "CRITICAL")
        assert len(cm.records) == 1
        assert cm.records[0].msg == "this is a critical-log"
        assert cm.records[0].levelname == "CRITICAL"

        with self.assertLogs("cnaas-nms", "ERROR") as cm:
            log("this is a error-log", "ERROR")
        assert len(cm.records) == 1
        assert cm.records[0].msg == "this is a error-log"
        assert cm.records[0].levelname == "ERROR"

    def test_log_incorrect_level(self):
        """Sending an invalid level logs with error and info"""
        with self.assertLogs("cnaas-nms", "INFO") as cm:
            log("this turns into a info-log", "INVALID_LEVEL")
        assert len(cm.records) == 2
        assert cm.records[0].msg == "INVALID_LEVEL is not a valid log level, defaulting to INFO."
        assert cm.records[0].levelname == "ERROR"
        assert cm.records[1].msg == "this turns into a info-log"
        assert cm.records[1].levelname == "INFO"

    def test_log_module_override(self):
        with self.assertLogs("cnaas-nms", "INFO") as cm:
            log("this is a custom info-log", module_override="info_log")
        # module_override is set to info_log.
        assert cm.records[0].module_override == "info_log"
        assert cm.records[0].levelname == "INFO"


def test_log_in_jinja(caplog):
    """
    Test logging within a jinja2 template.
    Uses pytest so we can use caplog fixture
    """
    env = Environment(autoescape=True)
    env.globals["log"] = log

    template = env.from_string('{{ log("test message", "INFO") }}')

    render = template.render()

    assert "test message" in caplog.text
    assert render == ""


if __name__ == "__main__":
    unittest.main()
