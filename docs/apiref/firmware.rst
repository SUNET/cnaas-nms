Firmware
========

The firmware API provides an interface to download, remove and list
firmware images which later can be used on managed devices.

Instead of uploading a file somewhere, you will have to tell this API
where to download the file from. The API will then schedule a job and
fetch the file and validate it towards the supplied SHA1 checksum.


Download firmware
-----------------

To download firmware from a URL, the following method can be used:

::
   
   curl https://hostname/api/v1.0/firmware -X POST -H "Content-Type: application/json" -d '{"url": "http://remote_host/firmware.bin", "sha1": "e0537400b5f134aa960603c9b715a8ce30306071"}'

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
   
   curl https://remote_host/api/v1.0/firmware/firmware.bin

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
    
