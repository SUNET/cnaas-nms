import logging
from typing import List

from flask import current_app

from cnaas_nms.scheduler.thread_data import thread_data
from cnaas_nms.tools.event import add_event


class CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord):
        self.records.append(record)


class WebsocketHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord):
        # Override module if module_override is set
        record.module = getattr(record, "module_override", record.module)

        msg = self.format(record)
        add_event(msg, level=record.levelname)


class StdoutHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord):
        # Override module if module_override is set
        record.module = getattr(record, "module_override", record.module)

        super().emit(record)


def get_logger():
    if hasattr(thread_data, "job_id") and type(thread_data.job_id) is int:
        logger = logging.getLogger("cnaas-nms-{}".format(thread_data.job_id))
        if not logger.handlers:
            formatter = logging.Formatter(
                "[%(asctime)s] %(levelname)s in %(module)s job #{}: %(message)s".format(thread_data.job_id)
            )
            # stdout logging
            stdout_handler = StdoutHandler()
            stdout_handler.setFormatter(formatter)
            logger.addHandler(stdout_handler)
            # websocket logging
            websocket_handler = WebsocketHandler()
            websocket_handler.setFormatter(formatter)
            logger.addHandler(websocket_handler)
    elif current_app:
        logger = current_app.logger
    else:
        logger = logging.getLogger("cnaas-nms")
        if not logger.handlers:
            formatter = logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
            # stdout logging
            stdout_handler = StdoutHandler()
            stdout_handler.setFormatter(formatter)
            logger.addHandler(stdout_handler)
            # websocket logging
            websocket_handler = WebsocketHandler()
            websocket_handler.setFormatter(formatter)
            logger.addHandler(websocket_handler)
    logger.setLevel(logging.DEBUG)  # TODO: get from /etc config ?
    return logger
