Firmware
========

The firmware API provides an interface to download, remove and list
firmware images which later can be used on managed devices.

Instead of uploading a file somewhere, you will have to tell this API
where to download the file from. The API will then schedule a job and
fetch the file and validate it towards the supplied SHA1 checksum.

When upgrading devices we can chose to either work on a single device
or a group of devices, this is described in more detailed further down
in this document.


Download firmware
-----------------

To download firmware from a URL, the following method can be used:

::

   curl https://hostname/api/v1.0/firmware -X POST -H "Content-Type: application/json" -d '{"url": "http://remote_host/firmware.bin", "sha1": "e0537400b5f134aa960603c9b715a8ce30306071", "verify_tls": false}'


The method will accept three attributes: url, sha1 and verify_tls:

* url: The URL to the file we should download.
* sha1: The checksum of the file.
* verify_tls: Should we validate SSL certificates or not?

That will schedule a new job which will report back the outcome of the download. The job status can be seen using the jobs API:

::

   curl https://hostname/api/v1.0/jobs?limit=1
   {
     "status": "success",
     "data": {
        "jobs": [
            {
                "id": "5d848e7cdd428720db72c686",
                "start_time": "2019-09-20 08:31:57.073000",
                "finish_time": "2019-09-20 08:31:58.585000",
                "status": "FINISHED",
                "function_name": "get_firmware",
                "result": "\"File downloaded from: https://remote_host/firmware.bin\"",
                "exception": null,
                "traceback": null,
                "next_job_id": null,
                "finished_devices": []
            }
        ]
      }
   }


List firmware
-------------

The same procedure as above can be used when listing the available
firmwares. The only difference is that when listing all available
firmware images no job is scheuled.


To list a single firmware image:

::

   curl https://hostname/api/v1.0/firmware/firmware.bin

   {
     "status": "success",
     "data": "Scheduled job get firmware information",
     "job_id": "5d848f87dd428720db72c68d"
   }

And the reponse when getting job information. Note that the result will contain the checksum of the images if it exists, otherwise an error will be given back.

::

   {
    "status": "success",
    "data": {
        "jobs": [
            {
                "id": "5d848f87dd428720db72c68d",
                "start_time": "2019-09-20 08:36:24.078000",
                "finish_time": "2019-09-20 08:36:24.110000",
                "status": "FINISHED",
                "function_name": "get_firmware_chksum",
                "result": "\"e0537400b5f134aa960603c9b715a8ce30306071\"",
                "exception": null,
                "traceback": null,
                "next_job_id": null,
                "finished_devices": []
            }
        ]
      }
   }


We can also list all available firmwares. Please note that here we
don't create a job. Here we don't get the checksum for all images,
since we don't want to waste cycles on computing that checksum for
each and every firmware.

::

   curl https://hostname/api/v1.0/firmware
   {
    "status": "success",
    "data": {
        "status": "success",
        "data": {
            "files": [
                "firmware.bin",
		"firmware2.bin"
            ]
          }
        }
    }


Remove firmware
---------------

To remove a firmware image:

::

   curl -X DELETE https://hostname/api/v1.0/firmware/firmware.bin
   {
    "status": "success",
    "data": "Scheduled job to remove firmware",
    "job_id": "5d849177dd428720db72c693"
   }


Upgrade firmware on device(s)
-----------------------------

As of today we support upgrading firmware on Arista EOS acces
switches. The upgrade procedure can do a 'pre-flight check' which will
make sure there is enough disk space before attempting to download the
firmware.

The API method will accept a few parameters:

* group: Optional. The name of a group, all devices in that group will be upgraded.
* hostname: Optional. If a hostname is specified, this single device will be upgraded.
* filename: Mandatory. Name of the new firmware, for example "test.swi".
* url: Optional, can also be configured as an environment variable, FIRMQRE_URL. URL to the firmware storage, for example "http://hostname/firmware/". This should typically point to the CNaaS NMS server and files will be downloaded from the CNaaS HTTP server.
* download: Optional, default is false. Only download the firmware.
* pre_flight: Optional, default is false. If true, check disk-space etc before downloading the firmware.
* post_flight: Optional, default is false. If true, update OS version after the upgrade have been finished.
* post_waittime: Optional, default is 0. Defines the time we should wait before trying to connect to an updated device.
* activate: Optional, default is false. Control whether we should install the new firmware or not.
* reboot: Optional, default is false. When the firmware is downloaded, reboot the switch.
* start_at: Schedule a firmware upgrade to be started sometime in the future.

An example CURL command can look like this:
::

   curl -k -s -H "Content-Type: application/json" -X POST https://hostname/api/v1.0/firmware/upgrade -d '{"group": "ACCESS", "filename": "test_firmware.swi", "url": "http://hostname/", "pre-flight": true, "download": true, "activate": true, "reboot": true, "start_at": "2019-12-24 00:00:00", "post_flight": true, "post_waittime": 600'}

The output from the job will look like this:

::

  {
    "status": "success",
    "data": {
      "jobs": [
        {
          "id": "5dcd110a5670fd67a615b089",
          "start_time": "2019-11-14 08:32:11.135000",
          "finish_time": "2019-11-14 08:34:50.352000",
          "status": "FINISHED",
          "function_name": "device_upgrade",
          "result": {
            "eoaccess": [
              {
                "name": "device_upgrade_task",
                "result": "",
                "diff": "",
                "failed": false
              },
              {
                "name": "arista_pre_flight_check",
                "result": "Pre-flight check done.",
                "diff": "",
                "failed": false
              },
              {
                "name": "arista_firmware_download",
                "result": "Firmware download done."
                "diff": "",
                "failed": false
              },
              {
                "name": "arista_firmware_activate",
                "result": "Firmware activate done.",
                "diff": "",
                "failed": false
              },
              {
                "name": "arista_device_reboot",
                "result": "Device reboot done.",
                "diff": "",
                "failed": false
              },
              {
                "result": "Post-flight, OS version updated for device eosaccess, now 4.23.2F-15405360.4232F.",
                "task_name": "arista_post_flight_check",
                "diff": "",
                "failed": false
              }
            ],
            "_totals": {
              "selected_devices": 1
            }
          },
          "exception": null,
          "traceback": null,
          "next_job_id": null,
          "finished_devices": [\"eosaccess\"]
        }
      ]
    }
  }
