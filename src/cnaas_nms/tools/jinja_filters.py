import ipaddress


def increment_ip(ip_string, increment=1):
    """Increment an IP address by a given value. Default increment value is 1."""
    ip = ipaddress.ip_address(ip_string)
    return format(ip + increment)


def increment_if(if_string, increment=1):
    """Increment an IP interface by a given value. Default increment value is 1.
    Args:
        if_string: Interface string, consisting of IP address + /prefix
        increment: Optional increment step, defaults to 1
    Returns:
        Interface string with incremented IP address
    """
    interface = ipaddress.ip_interface(if_string)
    network = interface.network
    address = interface.ip + increment

    # ugly workaround for IPv4: incrementing an interface's address changes the prefix in some
    # cases.
    # Check to ensure that the incremented address is in the original network.
    if not address in network.hosts():
        raise ValueError(f"IP address {address} is not in network {network.with_prefixlen}")
    else:
        return f"{address}/{network.prefixlen}"
