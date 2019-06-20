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
    curl https://localhost/api/v1.0/job?limit=1

The API call to device_syncto will start a job running in the background on the API server. To
show the progress/output of the job run the last command (/job) until you get a finished result.

Zero-touch provisioning of access switch
----------------------------------------

Power on switch, wait for it to boot using DHCP. List new devices that has booted using
CNaaS startup config::

    curl https://localhost/api/v1.0/device?filter=state,DISCOVERED

If the device serial/MAC matches with a device you want to provision, call the API to
initialize the device with a specified hostname and device type::

    curl https://localhost/api/v1.0/device_init/20 -d '{"hostname": "ex2300-top", "device_type": "ACCESS"}' -X POST -H "Content-Type: application/json"

Check job status to see progress, there should be two jobs running after each other, step1 and step2::

    curl https://localhost/api/v1.0/job?limit=2

