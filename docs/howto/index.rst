Howtos
======

Update settings for devices
---------------------------

Clone your settings repository in to a local directory. In this example we will use the
CNaaS provided example setting repository from github::

    git clone https://github.com/SUNET/cnaas-nms-settings
    cd cnaas-nms-settings
    vim access/base_system.yml
    <do some changes, save file>
    git commit -a -m "Updated setting for XYZ for access devices"
    git push

Tell the NMS API to fetch latest updates from the settings repo and try a sync to devices
with dry_run to preview changes::

    curl https://localhost/api/v1.0/repository/settings -d '{"action": "refresh"}' -X PUT -H "Content-Type: application/json"
    curl https://localhost/api/v1.0/device_syncto -d '{"hostname": "ex2300-top", "dry_run": true}' -X POST -H "Content-Type: application/json"
    curl https://localhost/api/v1.0/jobs?per_page=1&sort=-id

The API call to device_syncto will start a job running in the background on the API server. To
show the progress/output of the job run the last command (/job) until you get a finished result.

.. _ztp_intro:

Zero-touch provisioning of access switch
----------------------------------------

Power on the switch with a blank configuration and wait for it to boot, during
boot with a blank configuration it should ask for a DHCP on the native/untagged
VLAN. This DHCP request should then be forwarded to the server running the
CNaaS-NMS dhcpd container. The DHCP server will offer a lease to known vendor
devices and in the DHCP offer give them a path for a configuration file to
download. After the DHCP lease has been accepted the DHCP server will also
trigger the creation of a new device in the CNaaS-NMS database which will
save information on what MAC address the DHCP request was sent from, what IP
address was offered to the device, and set the state of the device to DHCP_BOOT.
The device should then download the configuration file specified from the DHCP
server, this configuration adds a dummy user account that will be used to
further configure the device. It will also ask the device to continue using
DHCP to aquire an IP address. When the device applies this new configuration a
new DHCP request will be sent to the DHCP server, and the DHCP server will
at that point trigger the CNaaS-NMS API to schedule a job to scan or "discover"
the new device. If the API can successfully reach the device it's serial number
and other data will be saved into the database and the state of the device
will be updated to "DISCOVERED". Now an operator can choose to continue
to provision the device.

List new devices that has booted using ZTP and reached the DISCOVERED state::

  curl https://localhost/api/v1.0/devices?filter[state]=DISCOVERED

Example output::

  {
    "status": "success",
    "data": {
      "devices": [
        {
          "id": 45,
          "hostname": "mac-B8C253EA5D52",
          "site_id": null,
          "description": null,
          "management_ip": null,
          "dhcp_ip": "192.168.0.240",
          "infra_ip": null,
          "oob_ip": null,
          "serial": "JW0218490737",
          "ztp_mac": "B8C253EA5D52",
          "platform": "junos",
          "vendor": "Juniper",
          "model": "EX2300-48P",
          "os_version": "18.4R1-S2.4",
          "synchronized": false,
          "state": "DISCOVERED",
          "device_type": "UNKNOWN",
          "confhash": null,
          "last_seen": "2019-09-20 10:33:44.265137",
          "port": null
        }
      ]
    }
  }

If the device serial/MAC matches with a device you want to provision, call the API to
initialize the device with a specified hostname and device type::

    curl https://localhost/api/v1.0/device_init/45 -d '{"hostname": "ex2300-top", "device_type": "ACCESS"}' -X POST -H "Content-Type: application/json"

Check job status to see progress, there should be two jobs running after each other, step1 and step2::

    curl https://localhost/api/v1.0/jobs?per_page=1&sort=-id

The first job will send a new base configuration to the device, this will move
the device management to a tagged VLAN and set a static IP address amongst
other things. The device will now move to state INIT.
After this change the TCP connection to the device will get
disconnected (since the IP was changed), this is expected. A new job (step2)
will be scheduled to run one minute later, this step2 job will try to log in
to the device using the new IP address and verify that the device accepted
the new configuration. If everything looks OK the device will move to the
state MANAGED.
If you have any plugins registered they will execute the "new_managed_device"
hook that can be used to add the device to monitoring systems etc at this point.


To debug this process it can be helpful to tail the logs from the DHCPd
container at the initial steps of the process, and also logs from the API
container at later stages of the process. If the device gets stuck in the
DHCP_BOOT process for example, it probably means the API can not log in to the
device using the credentials and IP address saved in the database. The API
will retry connecting to the device 5 times with increasing delay between
each attempt. If you want to trigger more retries at a later point you can manually
call the discover_device API call and send the MAC and DHCP IP of the device.


Zero-touch provisioning of fabric switch
----------------------------------------

You can also provision a new switch to be part of the (EVPN/VXLAN) fabric, that
is a switch with device_type DIST or CORE. Interfaces that connects between
CORE and DIST devices should be configured as ifclass "fabric" on both ends.
You can configure this in the settings repository via a device specific
setting or via a model specific setting (model setting might be preferable for
ZTP since you don't need to pre-provision new device hostnames in the settings
repository).

To verify that interfaces are configured correctly and that LLDP neighbors
are seen you can use the device_initcheck API call (see devices API reference):

::

   curl https://localhost/api/v1.0/device_initcheck/45 -d '{"hostname": "dist3", "device_type": "DIST"}' -X POST -H "Content-Type: application/json"

If all parameters are compatible you can start initialization:

::

   curl https://localhost/api/v1.0/device_init/45 -d '{"hostname": "dist3", "device_type": "DIST"}' -X POST -H "Content-Type: application/json"

If LLDP neighbors are not seen or are not of the expected type (DIST type
expect neighbors of type CORE and vice versa) you can manually specify the
neighbors you want to verify connectivity to, but make sure you know what you
are doing and maybe set up console access if something goes wrong here:

::

   curl https://localhost/api/v1.0/device_init/45 -d '{"hostname": "dist3", "device_type": "DIST", "neighbors": ["dist1", "dist2"]}' -X POST -H "Content-Type: application/json"

If you don't expect to see any LLDP neighbors at all and instead have
pre-configured some kind of uplink interfaces via ifclass custom interfaces
in settings for this device, you could also specify an empty list as
neighbors and in this case init will continue even if no LLDP neighbors were
detected. This is also very risky since you can't verify that interfaces
are connected correctly before sending configuration and possibly losing
connectivity to the device.
