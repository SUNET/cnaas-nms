import netaddr

def canonical_mac(mac):
    na_mac = netaddr.EUI(mac)
    na_mac.dialect = netaddr.mac_bare
    return str(na_mac)
