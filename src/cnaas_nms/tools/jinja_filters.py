"""Jinja filter functions for use in configuration templates"""

import ipaddress
import re
from typing import Union, Optional, Callable

# This global dict can be used to update the Jinja environment filters dict to include all
# registered template filter function
FILTERS = {}


def template_filter(name: Optional[str] = None) -> Callable:
    """Registers a template filter function in the FILTERS dict.

    Args:
        name: Optional alternative name to register the function as
    """

    def decorator(func):
        name_ = name if name else func.__name__
        FILTERS[name_] = func
        return func

    return decorator


@template_filter()
def increment_ip(ip_string, increment=1):
    """Increment an IP address by a given value. Default increment value is 1.
    Args:
        ip_string: IP address string. Can be plain or with numeric /prefix
        increment: Optional increment step, defaults to 1
    Returns:
        String with the incremented IP address, with optional numeric prefix
    """
    if '/' in ip_string:
        # IP with prefix
        interface = ipaddress.ip_interface(ip_string)
        address = interface.ip + increment

        # ugly workaround for IPv4: incrementing an interface's address changes the prefix in some
        # cases.
        # Check to ensure that the incremented address is in the original network.
        if not address in interface.network:
            raise ValueError(
                f"IP address {address} is not in network {interface.network.with_prefixlen}"
            )
        else:
            return f"{address}/{interface.network.prefixlen}"
    else:
        # plain IP
        ip = ipaddress.ip_address(ip_string)
        return format(ip + increment)


@template_filter()
def isofy_ipv4(ip_string, prefix=''):
    """Transform IPv4 address so it can be used as an ISO/NET address.
    All four blocks of the IP address are padded with zeros and split up into double octets.
    Example: 10.255.255.1 -> 0102.5525.5001.00
    With prefix: 10.255.255.1, 47.0023.0000.0001.0000 -> 47.0023.0000.0001.0000.0102.5525.5001.00
    Args:
        ip_string: a valid IPv4 address
        prefix: first part of the ISO address (optional)
    Returns:
        ISO address
    """
    ipaddress.IPv4Address(ip_string)  # fails for invalid IP

    if prefix != '':
        prefix_valid = bool(re.match('^.{2}(\..{4})*?$', prefix))
        if not prefix_valid:
            raise ValueError(f"{prefix} cannot be used as ISO prefix, please check formatting")
        prefix += '.'
    # IP: split and fill with 0s
    ip_parts = ip_string.split('.')
    padded = [p.zfill(3) for p in ip_parts]
    joined = ''.join(padded)
    # IP: split to chunks à 4 chars
    chunksize = 4
    ip_chunks = [joined[i : i + chunksize] for i in range(0, len(joined), chunksize)]
    # combine
    iso_address = prefix + '.'.join(ip_chunks) + '.00'
    return iso_address


@template_filter()
def ipv4_to_ipv6(
    v6_network: Union[str, ipaddress.IPv6Network], v4_address: Union[str, ipaddress.IPv4Interface]
):
    """Transforms an IPv4 address to an IPv6 interface address. This will combine an arbitrary
    IPv6 network address with the 32 address bytes of an IPv4 address into a valid IPv6 address
    + prefix length notation - the equivalent of dotted quad compatible notation.

    E.g.:
    >>> ipv6 = ipv4_to_ipv6("2001:700:dead:babe::/64", "127.0.0.1")
    >>> ipv6
    IPv6Interface('2001:700:dead:babe::7f00:1/64')
    >>> ipv6 == ipaddress.IPv6Interface('2001:700:dead:babe::127.0.0.1/64')
    True

    Args:
        v6_network: IPv6 network in prefix notation
        v4_address: IPv4 address
    Returns:
        An IPv6Address object on the given network
    """
    if isinstance(v6_network, str):
        v6_network = ipaddress.IPv6Network(v6_network)
    if isinstance(v4_address, str):
        v4_address = ipaddress.IPv4Address(v4_address)

    v6_address = v6_network[int(v4_address)]
    return ipaddress.IPv6Interface(f"{v6_address}/{v6_network.prefixlen}")


@template_filter()
def get_interface(
    network: Union[ipaddress.IPv6Interface, ipaddress.IPv4Interface, str], index: int
) -> Union[ipaddress.IPv6Interface, ipaddress.IPv4Interface]:
    """Returns a host address with a prefix length from its index in a network.

    Example:
    >>> get_interface("10.0.1.0/24", 2)
    ipaddress.IPv4Interface("10.0.1.2/24")

    Args:
        network: Network in CIDR notation
        index: The host address' index in the network prefix
    """
    if isinstance(network, str):
        network = ipaddress.ip_network(network)

    host = network[index]
    return ipaddress.ip_interface(f"{host}/{network.prefixlen}")
