import ipaddress


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
