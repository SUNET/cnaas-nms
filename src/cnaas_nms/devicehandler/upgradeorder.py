from cnaas_nms.db.device import Device, DeviceType


def determine_upgrade_order(session, devices: list[Device]) -> list[list[Device]]:
    """
    Determine the upgrade order for the devices.
    """
    # find devices that have neighbors of type DIST
    ret: list[list[Device]] = []
    remaining_devices: set[Device] = set(devices)
    has_dist_neighbors = []
    mlag_pairs: list[list[Device]] = []
    included_device_types = set()
    for device in devices:
        included_device_types.add(device.device_type)
        for neighbor in device.get_neighbors(session):
            if neighbor.device_type == DeviceType.DIST:
                has_dist_neighbors.append(device)
        mlag_peer = device.get_mlag_peer(session)
        if mlag_peer and mlag_peer in devices:
            pair = sorted([device, mlag_peer], key=lambda d: d.hostname)
            if pair not in mlag_pairs:
                mlag_pairs.append(pair)

    if included_device_types == {DeviceType.ACCESS}:
        # all devices are access devices
        mlag = False
        for pair in mlag_pairs:
            # make sure ret includes at least two empty lists
            if len(ret) == 0:
                ret.append([])
            if len(ret) == 1:
                ret.append([])

            ret[0].append(pair[0])
            ret[1].append(pair[1])
            remaining_devices.remove(pair[0])
            remaining_devices.remove(pair[1])
            mlag = True

        for device in has_dist_neighbors:
            if len(ret) == 0:
                ret.append([])
            if device in remaining_devices:
                ret[0].append(device)
                remaining_devices.remove(device)

        while remaining_devices:
            # find devices with neighbors in the last added group
            group_devices = set()
            for device in remaining_devices:
                for neighbor in device.get_neighbors(session):
                    if neighbor in ret[-1]:
                        group_devices.add(device)
                    if mlag and neighbor in ret[-2]:
                        group_devices.add(device)
            mlag = False  # only match first group for the top-level MLAG pair
            if not group_devices:
                raise ValueError("No devices with neighbors in the last added group found in ACCESS-only upgrade group")

            remaining_devices -= group_devices
            ret.append(list(group_devices))

        return ret
    else:
        raise NotImplementedError("Upgrade order determination is only supported for ACCESS-only device groups")
