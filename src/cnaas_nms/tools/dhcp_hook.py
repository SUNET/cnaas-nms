#!/usr/bin/env python3

import sys

import cnaas_nms.db.helper
from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.session import sqla_session
from cnaas_nms.tools.log import get_logger

logger = get_logger()

if len(sys.argv) < 3:
    sys.exit(1)
if sys.argv[1] == "commit":
    try:
        ztp_mac = cnaas_nms.db.helper.canonical_mac(sys.argv[2])
        dhcp_ip = sys.argv[3]
        platform = sys.argv[4]
    except Exception as e:
        print(str(e))
        sys.exit(2)
    with sqla_session() as session:
        db_entry: Device = session.query(Device).filter(Device.ztp_mac==ztp_mac).first()
        if db_entry:
            if db_entry.state == DeviceState.DHCP_BOOT:
                db_entry.state = DeviceState.DISCOVERED
                db_entry.dhcp_ip = dhcp_ip
                logger.info("New device booted via DHCP to state DISCOVERED: {}".format(
                    ztp_mac
                ))
            else:
                logger.error("New device booted via DHCP in unhandled state {}: {}".format(
                    db_entry.state,
                    ztp_mac
                ))
        else:
            # TODO: look for entries with same dhcp_ip in DB and set them to null (they are stale)
            new_device = Device()
            new_device.ztp_mac = ztp_mac
            new_device.dhcp_ip = dhcp_ip
            new_device.hostname = f'mac-{ztp_mac}'
            new_device.platform = platform
            new_device.state = DeviceState.DHCP_BOOT
            new_device.device_type = DeviceType.UNKNOWN
            session.add(new_device)
            logger.info("New device booted via DHCP to state DHCP_BOOT: {}".format(
                ztp_mac
            ))
