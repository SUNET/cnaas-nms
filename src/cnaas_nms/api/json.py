"""Custom JSON encoder utilities for API"""

import json
from ipaddress import _IPAddressBase


class CNaaSJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, _IPAddressBase):
            return str(o)
        else:
            return super().default(self, o)
