import copy
from typing import List

from netutils.interface import interface_range_expansion

from cnaas_nms.tools.log import get_logger


def expand_interface_settings(interfaces: List[dict]) -> List[dict]:
    """Expand interface ranges into individual interfaces"""
    logger = get_logger()
    expanded_interfaces = []
    for intf_range in interfaces:
        expanded_names = interface_range_expansion(intf_range["name"])
        if len(expanded_names) > 1:
            logger.debug(
                "Expanding interface range '{}' into parts: {}".format(intf_range["name"], ", ".join(expanded_names))
            )
        for individual_name in expanded_names:
            expanded_intf = copy.deepcopy(intf_range)
            expanded_intf["name"] = individual_name
            expanded_interfaces.append(expanded_intf)
    return expanded_interfaces
