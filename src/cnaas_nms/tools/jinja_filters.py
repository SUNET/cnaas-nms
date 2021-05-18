import ipaddress
import re


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


def ipv4_to_ipv6(v6network_string, v4address):
    """Transform IPv4 address to IPv6. This will combine four hextets of an IPv6 network
    with four pseudo-hextets of an IPv4 address into a valid IPv6 address.
    Args:
        v6network_string: IPv6 network in prefix notation
        v4address: IPv4 address
    Returns:
        IPv6 address on the given network, in compressed notation
    """
    v6network = ipaddress.IPv6Network(v6network_string)
    part1 = v6network.network_address.compressed
    part3 = v6network.prefixlen
    part2 = v4address.replace('.', ':')
    v6address_string = f"{part1}{part2}/{part3}"

    v6address = ipaddress.IPv6Interface(v6address_string)
    assert v6address in v6network  # verify that address is on the given network

    return v6address.compressed
