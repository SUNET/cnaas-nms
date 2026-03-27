from typing import Union

import pytest

from cnaas_nms.db.device import Device, DeviceState, DeviceType
from cnaas_nms.db.interface import Interface, InterfaceConfigType
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.session import sqla_session
from cnaas_nms.devicehandler.upgradeorder import determine_upgrade_order


@pytest.mark.integration
def test_topology_mlag():
    topology = {"devices": [], "linknets": [], "connected_devices": [], "interfaces": [], "expected_order": []}
    dist_device1 = Device(hostname="d1", platform="eos", device_type=DeviceType.DIST, state=DeviceState.MANAGED)
    dist_device2 = Device(hostname="d2", platform="eos", device_type=DeviceType.DIST, state=DeviceState.MANAGED)
    access_device_mlag1 = Device(
        hostname="mlag-a1", platform="eos", device_type=DeviceType.ACCESS, state=DeviceState.MANAGED
    )
    access_device_mlag2 = Device(
        hostname="mlag-a2", platform="eos", device_type=DeviceType.ACCESS, state=DeviceState.MANAGED
    )
    access_device_mlag11 = Device(
        hostname="mlag-a11", platform="eos", device_type=DeviceType.ACCESS, state=DeviceState.MANAGED
    )
    access_level2_1 = Device(hostname="a3", platform="eos", device_type=DeviceType.ACCESS, state=DeviceState.MANAGED)
    access_level2_2 = Device(hostname="a4", platform="eos", device_type=DeviceType.ACCESS, state=DeviceState.MANAGED)
    access_level3_1 = Device(hostname="a30", platform="eos", device_type=DeviceType.ACCESS, state=DeviceState.MANAGED)

    mlag_linknet1: Linknet = Linknet(
        device_a=access_device_mlag1,
        device_b=access_device_mlag2,
        device_a_port="Ethernet25",
        device_b_port="Ethernet25",
    )
    mlag_linknet2: Linknet = Linknet(
        device_a=access_device_mlag1,
        device_b=access_device_mlag2,
        device_a_port="Ethernet26",
        device_b_port="Ethernet26",
    )
    dist_uplink_linknet1: Linknet = Linknet(
        device_a=dist_device1, device_b=access_device_mlag1, device_a_port="Ethernet1", device_b_port="Ethernet49"
    )
    dist_uplink_linknet2: Linknet = Linknet(
        device_a=dist_device2, device_b=access_device_mlag2, device_a_port="Ethernet1", device_b_port="Ethernet49"
    )
    dist_uplink_linknet11: Linknet = Linknet(
        device_a=dist_device1, device_b=access_device_mlag11, device_a_port="Ethernet2", device_b_port="Ethernet49"
    )
    access_level2_1_linknet1: Linknet = Linknet(
        device_a=access_device_mlag1, device_b=access_level2_1, device_a_port="Ethernet1", device_b_port="Ethernet49"
    )
    access_level2_1_linknet2: Linknet = Linknet(
        device_a=access_device_mlag2, device_b=access_level2_1, device_a_port="Ethernet1", device_b_port="Ethernet50"
    )
    access_level2_2_linknet: Linknet = Linknet(
        device_a=access_device_mlag1, device_b=access_level2_2, device_a_port="Ethernet2", device_b_port="Ethernet49"
    )
    access_level3_1_linknet: Linknet = Linknet(
        device_a=access_level2_1, device_b=access_level3_1, device_a_port="Ethernet1", device_b_port="Ethernet49"
    )

    topology["devices"].extend(
        [
            access_device_mlag1,
            access_device_mlag2,
            access_device_mlag11,
            access_level2_1,
            access_level2_2,
            access_level3_1,
        ]
    )
    topology["linknets"].extend(
        [
            mlag_linknet1,
            mlag_linknet2,
            dist_uplink_linknet1,
            dist_uplink_linknet2,
            dist_uplink_linknet11,
            access_level2_1_linknet1,
            access_level2_1_linknet2,
            access_level2_2_linknet,
            access_level3_1_linknet,
        ]
    )
    topology["connected_devices"].extend([dist_device1, dist_device2])
    topology["expected_order"].extend(
        [
            {access_device_mlag1, access_device_mlag11},
            {access_device_mlag2},
            {access_level2_1, access_level2_2},
            {access_level3_1},
        ]
    )

    mlag_peer1_if1 = Interface(device=access_device_mlag1, name="Ethernet25", configtype=InterfaceConfigType.MLAG_PEER)
    mlag_peer1_if2 = Interface(device=access_device_mlag1, name="Ethernet26", configtype=InterfaceConfigType.MLAG_PEER)
    mlag_peer2_if1 = Interface(device=access_device_mlag2, name="Ethernet25", configtype=InterfaceConfigType.MLAG_PEER)
    mlag_peer2_if2 = Interface(device=access_device_mlag2, name="Ethernet26", configtype=InterfaceConfigType.MLAG_PEER)
    topology["interfaces"].extend([mlag_peer1_if1, mlag_peer1_if2, mlag_peer2_if1, mlag_peer2_if2])

    verify_upgrade_order(topology)


@pytest.mark.integration
def test_topology_access():
    topology = {"devices": [], "linknets": [], "connected_devices": [], "interfaces": [], "expected_order": []}
    dist_device1 = Device(hostname="d1", platform="eos", device_type=DeviceType.DIST, state=DeviceState.MANAGED)
    dist_device2 = Device(hostname="d2", platform="eos", device_type=DeviceType.DIST, state=DeviceState.MANAGED)
    access_device1 = Device(hostname="a1", platform="eos", device_type=DeviceType.ACCESS, state=DeviceState.MANAGED)
    access_device2 = Device(hostname="a2", platform="eos", device_type=DeviceType.ACCESS, state=DeviceState.MANAGED)
    access_device3 = Device(hostname="a3", platform="eos", device_type=DeviceType.ACCESS, state=DeviceState.MANAGED)
    access_level2_1 = Device(hostname="a10", platform="eos", device_type=DeviceType.ACCESS, state=DeviceState.MANAGED)
    access_level2_2 = Device(hostname="a20", platform="eos", device_type=DeviceType.ACCESS, state=DeviceState.MANAGED)

    dist_uplink_linknet1_1: Linknet = Linknet(
        device_a=dist_device1, device_b=access_device1, device_a_port="Ethernet1", device_b_port="Ethernet49"
    )
    dist_uplink_linknet1_2: Linknet = Linknet(
        device_a=dist_device2, device_b=access_device1, device_a_port="Ethernet1", device_b_port="Ethernet50"
    )
    dist_uplink_linknet2_1: Linknet = Linknet(
        device_a=dist_device1, device_b=access_device2, device_a_port="Ethernet2", device_b_port="Ethernet49"
    )
    dist_uplink_linknet2_2: Linknet = Linknet(
        device_a=dist_device2, device_b=access_device2, device_a_port="Ethernet2", device_b_port="Ethernet50"
    )
    dist_uplink_linknet3_1: Linknet = Linknet(
        device_a=dist_device1, device_b=access_device3, device_a_port="Ethernet3", device_b_port="Ethernet49"
    )
    dist_uplink_linknet3_2: Linknet = Linknet(
        device_a=dist_device2, device_b=access_device3, device_a_port="Ethernet3", device_b_port="Ethernet50"
    )
    access_level2_1_linknet1: Linknet = Linknet(
        device_a=access_device1, device_b=access_level2_1, device_a_port="Ethernet1", device_b_port="Ethernet49"
    )
    access_level2_2_linknet: Linknet = Linknet(
        device_a=access_device2, device_b=access_level2_2, device_a_port="Ethernet2", device_b_port="Ethernet49"
    )

    topology["devices"].extend(
        [
            access_device1,
            access_device2,
            access_device3,
            access_level2_1,
            access_level2_2,
        ]
    )
    topology["linknets"].extend(
        [
            dist_uplink_linknet1_1,
            dist_uplink_linknet1_2,
            dist_uplink_linknet2_1,
            dist_uplink_linknet2_2,
            dist_uplink_linknet3_1,
            dist_uplink_linknet3_2,
            access_level2_1_linknet1,
            access_level2_2_linknet,
        ]
    )
    topology["connected_devices"].extend([dist_device1, dist_device2])
    topology["expected_order"].extend(
        [
            {access_device1, access_device2, access_device3},
            {access_level2_1, access_level2_2},
        ]
    )

    verify_upgrade_order(topology)


def verify_upgrade_order(testtopology: dict[str, Union[list[Device], list[list[Device]], list[Linknet]]]):
    with sqla_session() as session:
        try:
            for dev in testtopology["devices"]:
                session.add(dev)
            for dev in testtopology["connected_devices"]:
                session.add(dev)
            session.flush()
            for link in testtopology["linknets"]:
                session.add(link)
            session.flush()
            for intf in testtopology["interfaces"]:
                session.add(intf)
            session.flush()

            upgrade_order = determine_upgrade_order(session, testtopology["devices"])
            for index, item in enumerate(testtopology["expected_order"]):
                assert set(item) == set(upgrade_order[index]), "Upgrade order is not correct"
            print(f"Upgrade order: {upgrade_order}")
        finally:
            session.rollback()
