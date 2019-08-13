import logging

from cnaas_nms.plugins.pluginspec import CnaasBasePlugin, hookimpl


class Plugin(CnaasBasePlugin):
    @hookimpl
    def selftest(self):
        vars = self.get_vars(__name__)
        print("vars: {}".format(vars))
        logger = logging.getLogger("filewriter")
        try:
            handler = logging.FileHandler(vars['logfile'])
        except PermissionError:
            return False
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.info("Staring filewriter")
        return True
