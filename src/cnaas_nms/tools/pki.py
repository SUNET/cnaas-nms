import datetime
import os
import ssl
from ipaddress import IPv4Address

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from cnaas_nms.app_settings import api_settings
from cnaas_nms.tools.log import get_logger

logger = get_logger()


def get_ssl_context():
    new_ssl_context = None

    if api_settings.CAFILE:
        if os.path.isfile(api_settings.CAFILE):
            new_ssl_context = ssl.create_default_context(cafile=api_settings.CAFILE)
        else:
            logger.error("Specified cafile is not a file: {}".format(api_settings.CAFILE))

    if not api_settings.VERIFY_TLS_DEVICE:
        logger.warning("Accepting unverified TLS certificates")
        new_ssl_context = ssl._create_unverified_context()  # noqa: S323

    if not new_ssl_context:
        logger.debug("Using system default CAs")
        new_ssl_context = ssl.create_default_context()

    return new_ssl_context


def generate_device_cert(hostname: str, ipv4_address: IPv4Address):
    try:
        if not os.path.isfile(api_settings.CAFILE):
            raise Exception("Specified cafile is not a file: {}".format(api_settings.CAFILE))
    except KeyError:
        raise Exception("No cafile specified in api.yml")

    try:
        if not os.path.isfile(api_settings.CAKEYFILE):
            raise Exception("Specified cakeyfile is not a file: {}".format(api_settings.CAKEYFILE))
    except KeyError:
        raise Exception("No cakeyfile specified in api.yml")

    try:
        if not os.path.isdir(api_settings.CERTPATH):
            raise Exception("Specified certpath is not a directory")
    except KeyError:
        raise Exception("No certpath found in API settings")

    with open(api_settings.CAKEYFILE, "rb") as cakeyfile:
        root_key = serialization.load_pem_private_key(
            cakeyfile.read(),
            password=None,
        )

    with open(api_settings.CAFILE, "rb") as cafile:
        root_cert = x509.load_pem_x509_certificate(cafile.read())

    cert_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
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

    with open(os.path.join(api_settings.CERTPATH, "{}.crt".format(hostname)), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(os.path.join(api_settings.CERTPATH, "{}.key".format(hostname)), "wb") as f:
        f.write(
            cert_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )


ssl_context = get_ssl_context()
