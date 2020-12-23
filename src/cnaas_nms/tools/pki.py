import ssl
import os
import datetime
from ipaddress import IPv4Address

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

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

    if 'verify_tls_device' in apidata and type(apidata['verify_tls_device']) == bool and \
            not apidata['verify_tls_device']:
        logger.warning("Accepting unverified TLS certificates")
        new_ssl_context = ssl._create_unverified_context()

    if not new_ssl_context:
        logger.debug("Using system default CAs")
        new_ssl_context = ssl.create_default_context()

    return new_ssl_context


def generate_device_cert(hostname: str, ipv4_address: IPv4Address):
    apidata = get_apidata()
    try:
        if not os.path.isfile(apidata['cafile']):
            raise Exception("Specified cafile is not a file: {}".format(apidata['cafile']))
    except KeyError:
        raise Exception("No cafile specified in api.yml")

    try:
        if not os.path.isfile(apidata['cakeyfile']):
            raise Exception("Specified cakeyfile is not a file: {}".format(apidata['cakeyfile']))
    except KeyError:
        raise Exception("No cakeyfile specified in api.yml")

    try:
        if not os.path.isdir(apidata['certpath']):
            raise Exception("Specified certpath is not a directory")
    except KeyError:
        raise Exception("No certpath found in api.yml settings")

    with open(apidata['cakeyfile'], "rb") as cakeyfile:
        root_key = serialization.load_pem_private_key(
            cakeyfile.read(),
            password=None,
        )

    with open(apidata['cafile'], "rb") as cafile:
        root_cert = x509.load_pem_x509_certificate(
            cafile.read()
        )

    cert_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    new_subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(new_subject)
        .issuer_name(root_cert.issuer)
        .public_key(cert_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=7300))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipv4_address)]),
            critical=False,
        )
        .sign(root_key, hashes.SHA256(), default_backend())
    )

    with open(os.path.join(apidata['certpath'], "{}.crt".format(hostname)), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(os.path.join(apidata['certpath'], "{}.key".format(hostname)), "wb") as f:
        f.write(cert_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))


ssl_context = get_ssl_context()
