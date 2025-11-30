import unittest

from jinja2 import Environment
from jinja2.exceptions import TemplateError

from cnaas_nms.tools.jinja_functions import (
    log,
    raise_helper,
)


class RaiseTests(unittest.TestCase):
    def test_raise_helper(self):
        with self.assertRaises(TemplateError) as cm:
            raise_helper("this raises TemplateError")
        assert cm.exception.message == "this raises TemplateError"

    def test_raise_in_jinja(self):
        env = Environment(autoescape=True)
        env.globals["raise"] = raise_helper

        template = env.from_string('{{ raise("some exception") }}')

        with self.assertRaises(TemplateError) as cm:
            template.render()
        assert cm.exception.message == "some exception"

    def test_raise_in_jinja_if_else(self):
        """Raise exception only when caught in jinja if/else"""
        env = Environment(autoescape=True)
        env.globals["raise"] = raise_helper

        template = env.from_string(
            """
                {%- if host == "d1" -%}
                 {{ raise("d1 is not valid") }}
                {%- else -%}
                some text
                {%- endif -%}
            """
        )

        with self.assertRaises(TemplateError) as cm:
            template.render(host="d1")
        assert cm.exception.message == "d1 is not valid"
        assert "some text" == template.render(host="a1")


def test_log_info(caplog):
    with caplog.at_level("INFO", logger="cnaas-nms"):
        log("this is a info-log")
        log("this is also a info-log", "info")

    assert len(caplog.records) == 2
    assert caplog.records[0].msg == "this is a info-log"
    assert caplog.records[0].levelname == "INFO"


def test_log_warning(caplog):
    with caplog.at_level("WARNING", logger="cnaas-nms"):
        log("this is a warning-log", "WARNING")

    assert len(caplog.records) == 1
    assert caplog.records[0].msg == "this is a warning-log"
    assert caplog.records[0].levelname == "WARNING"


def test_log_critical(caplog):
    with caplog.at_level("CRITICAL", logger="cnaas-nms"):
        log("this is a critical-log", "CRITICAL")

    assert len(caplog.records) == 1
    assert caplog.records[0].msg == "this is a critical-log"
    assert caplog.records[0].levelname == "CRITICAL"


def test_log_error(caplog):
    with caplog.at_level("ERROR", logger="cnaas-nms"):
        log("this is a error-log", "ERROR")

    assert len(caplog.records) == 1
    assert caplog.records[0].msg == "this is a error-log"
    assert caplog.records[0].levelname == "ERROR"


def test_log_incorrect_level(caplog):
    """Sending an invalid level logs with error and info"""
    with caplog.at_level("INFO", logger="cnaas-nms"):
        log("this turns into a info-log", "INVALID_LEVEL")

    # Expect two logs: error + defaulted info
    assert len(caplog.records) == 2
    assert caplog.records[0].msg == "INVALID_LEVEL is not a valid log level, defaulting to INFO."
    assert caplog.records[0].levelname == "ERROR"
    assert caplog.records[1].msg == "this turns into a info-log"
    assert caplog.records[1].levelname == "INFO"


def test_log_module_override(caplog):
    with caplog.at_level("INFO", logger="cnaas-nms"):
        log("this is a custom info-log", module_override="info_log")

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert getattr(record, "module_override", None) == "info_log"
    assert record.levelname == "INFO"


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


def test_log_in_jinja_if_else(caplog):
    """Log only when caught in if/else"""
    env = Environment(autoescape=True)
    env.globals["log"] = log

    template = env.from_string(
        """
            {%- if host == "d1" -%}
             {{ log("d1 is not valid") }}
            {%- else -%}
            some text
            {%- endif -%}
        """
    )

    render1 = template.render(host="d1")
    render2 = template.render(host="a1")
    assert len(caplog.records) == 1
    assert "d1 is not valid" == caplog.records[0].message
    assert render1 == ""
    assert render2 == "some text"


if __name__ == "__main__":
    unittest.main()
