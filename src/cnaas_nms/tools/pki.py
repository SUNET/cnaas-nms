import ssl
import os

from cnaas_nms.tools.get_apidata import get_apidata
from cnaas_nms.tools.log import get_logger

logger = get_logger()


def get_ssl_context():
    apidata = get_apidata()
    new_ssl_context = None

    if 'cafile' in apidata:
        if os.path.isfile(apidata['cafile']):
            new_ssl_context = ssl.create_default_context(cafile=apidata['cafile'])
        else:
            logger.error("Specified cafile is not a file: {}".format(apidata['cafile']))

    if 'verify_tls' in apidata and type(apidata['verify_tls']) == bool and not apidata['verify_tls']:
        logger.warning("Accepting unverified TLS certificates")
        new_ssl_context = ssl._create_unverified_context()

    if not new_ssl_context:
        logger.debug("Using system default CAs")
        new_ssl_context = ssl.create_default_context()

    return new_ssl_context


ssl_context = get_ssl_context()
