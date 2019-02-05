from nornir import InitNornir

from nornir.core.deserializer.inventory import Inventory

def cnaas_init():
    nr = InitNornir(
        inventory={
            "plugin": "cnaas_nms.confpush.nornir_plugins.cnaas_inventory.CnaasInventory"
        }
    )
    return nr
