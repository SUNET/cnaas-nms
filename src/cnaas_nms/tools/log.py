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

class CustomFormatter(logging.Formatter):

    main_format  = '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    job_format  = '[%(asctime)s] %(levelname)s in %(module)s job #%(jobid)s: %(message)s'

    def __init__(self):
        super().__init__()  
    
    def format(self, record):
        # include jobid in log line if it it exists
        if hasattr(record, 'jobid'):
            self._style._fmt = CustomFormatter.job_format
        else:
            self._style._fmt = CustomFormatter.main_format
        result = logging.Formatter.format(self, record)
        return result

def init_logger():
    logger = logging.getLogger('cnaas-nms')
    logger.setLevel(logging.DEBUG)
    formatter = CustomFormatter()
    for handler in [logging.StreamHandler(), WebsocketHandler()]:
        handler.setFormatter(formatter)
        logger.addHandler(handler)

def get_logger():
    extra = {}
    if hasattr(thread_data, 'job_id') and type(thread_data.job_id) == int:
        extra['jobid'] = thread_data.job_id
    elif current_app:
        return current_app.logger
    logger = logging.getLogger('cnaas-nms')
    return logging.LoggerAdapter(logger, extra)
