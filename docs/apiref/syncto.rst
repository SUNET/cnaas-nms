Sync to device
==============

To make the network devices synchronize their configuration to the latest version generated
by CNaaS the device_syncto API call is used. This will push the latest configuration to
the devices you select.

You can choose to either synchronize all devices, or just synchronize a specific type of device,
or synchronize just a specific hostname.

Example API call:

::

   curl https://hostname/api/v1.0/device_syncto -d '{"hostname": "eosdist", "dry_run": true}'
   -X POST -H "Content-Type: application/json"

This will start a "dry run" synchronization job for the device called "eosdist". A dry run job
will send the newly generated configuration to the device and then generate a diff to see
what lines would have been changed. The response from this API call is a reference to a job id
that you can poll using the job API. This is to make sure that long running jobs does not block
the client. If you synchronize many devices at the same time the job can take a very long time
and the client might time out otherwise.

Example response:

::

  {
    "status": "success",
    "data": "Scheduled job to synchronize eosdist",
    "job_id": "5d5aa787ba050d5fd085f1ce"
  }

The status success in this case only means that the job was scheduled successfully, but
you have to poll the job API to see that result of what was done, the job itself might still
fail.

Arguments:
----------

 - hostname: Optional, the hostname of a device
 - device_type: Optional, a device type (access, dist or core)
 - dry_run: Dry run does not commit any configuration to the device. Boolean, defaults to true.
 - force: If a device configuration has been changed outside of CNaaS the configuration hash
   will differ from the last known hash in the database and this will normally make CNaaS
   abort. If you want to override any changes made outside of CNaaS and replace them with the
   latest configuration from CNaaS you can set this flag to true. Boolean, defaults to false.
 - auto_push: If you specify a single device by hostname and do a dry_run, setting this option
   will cause CNaaS to automatically push the configuration to committed/live state after
   doing the dry run if the change impact score (see :ref:`change_impact_score`) is very low.

If neither hostname or device_type is specified all devices that needs to be sycnhronized
will be selected.
