import logging

from cnaas_nms.plugins.pluginspec import CnaasBasePlugin, hookimpl
from cnaas_nms.tools.log import get_logger


logger = get_logger()


class Plugin(CnaasBasePlugin):
    @classmethod
    def get_logger(cls):
        pluginvars = cls.get_vars(__name__)
        file_logger = logging.getLogger("filewriter")
        if not file_logger.handlers:
            try:
                handler = logging.FileHandler(pluginvars['logfile'])
            except PermissionError:
                logger.error("Permission denied for logfile: {}".format(pluginvars['logfile']))
                return None
            file_logger.addHandler(handler)
        file_logger.setLevel(logging.DEBUG)
        return file_logger

    @hookimpl
    def selftest(self):
        file_logger = self.get_logger()
        if file_logger:
            file_logger.info("Staring filewriter")
            return True
        else:
            return False

    @hookimpl
    def allocated_ipv4(self, vrf, ipv4_address, ipv4_network, hostname):
        file_logger = self.get_logger()
        file_logger.info("{} {} {} {}".format(vrf, ipv4_address, ipv4_network, hostname))

    @hookimpl
    def new_managed_device(self, hostname, device_type, serial_number, vendor,
                           model, os_version):
        file_logger = self.get_logger()
        file_logger.info("{} {} {} {} {} {}".format(hostname, device_type, serial_number,
                                                    vendor, model, os_version))
