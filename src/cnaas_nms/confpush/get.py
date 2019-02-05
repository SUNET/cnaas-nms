from nornir import InitNornir

from nornir.core.deserializer.inventory import Inventory

import cnaas_nms.confpush.nornir_helper

def get_inventory():
    nr = cnaas_nms.confpush.nornir_helper.cnaas_init()
    return Inventory.serialize(nr.inventory).dict()
