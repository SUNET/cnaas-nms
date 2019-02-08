def canonical_mac(mac):
    #TODO: use something better.. netaddr?
    return mac.replace(':', '').replace('-', '').replace('.','').upper()
