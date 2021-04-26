import ipaddress

def increment_ip(ip_string, increment=1):
    """Increment an IP address by a given value. Default increment value is 1."""
    ip = ipaddress.ip_address(ip_string)
    return format(ip + increment)
