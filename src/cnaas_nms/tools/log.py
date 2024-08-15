import logging

from flask import current_app

from cnaas_nms.scheduler.thread_data import thread_data
from cnaas_nms.tools.event import add_event


class WebsocketHandler(logging.StreamHandler):
    def __init__(self):
        logging.StreamHandler.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        add_event(msg, level=record.levelname)


def get_logger():
    if hasattr(thread_data, "job_id") and type(thread_data.job_id) is int:
        logger = logging.getLogger("cnaas-nms-{}".format(thread_data.job_id))
        if not logger.handlers:
            formatter = logging.Formatter(
                "[%(asctime)s] %(levelname)s in %(module)s job #{}: %(message)s".format(thread_data.job_id)
            )
            # stdout logging
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            # websocket logging
            handler = WebsocketHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
    elif current_app:
        logger = current_app.logger
    else:
        logger = logging.getLogger("cnaas-nms")
        if not logger.handlers:
            formatter = logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
            # stdout logging
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            # websocket logging
            handler = WebsocketHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)  # TODO: get from /etc config ?
    return logger
