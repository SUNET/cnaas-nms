import logging

from flask import current_app

import cnaas_nms.api.app


class WebsocketHandler(logging.StreamHandler):
    def __init__(self):
        logging.StreamHandler.__init__(self)

    def socketio_emit(self, msg, rooms=[]):
        if cnaas_nms.api.app.socketio:
            for room in rooms:
                cnaas_nms.api.app.socketio.emit('cnaas_log', msg, room=room)

    def emit(self, record):
        msg = self.format(record)
        if record.levelname == 'DEBUG':
            self.socketio_emit(msg, rooms=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        elif record.levelname == 'INFO':
            self.socketio_emit(msg, rooms=['INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        elif record.levelname == 'WARNING':
            self.socketio_emit(msg, rooms=['WARNING', 'ERROR', 'CRITICAL'])
        elif record.levelname == 'ERROR':
            self.socketio_emit(msg, rooms=['ERROR', 'CRITICAL'])
        elif record.levelname == 'CRITICAL':
            self.socketio_emit(msg, rooms=['CRITICAL'])


def get_logger():
    if current_app:
        logger = current_app.logger
    else:
        logger = logging.getLogger('cnaas-nms')
        if not logger.handlers:
            formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
            # stdout logging
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            # websocket logging
            handler = WebsocketHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
    logger.setLevel(logging.DEBUG) #TODO: get from /etc config ?
    return logger
