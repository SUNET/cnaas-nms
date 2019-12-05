Jobs
====

The jobs API can retreive information about jobs in CNaaS-NMS, any task that takes more
than a few seconds to complete or needs specific scheduling requirements will be executed
as a job in CNaaS-NMS. A job will always be in one of these states:

- SCHEDULED: The job has been scheduled to run at a later time
- RUNNING: The job is currently running
- FINISHED: The job has completed, all parts were executed but some parts might have errors
- EXCEPTION: The job has stopped with an error/exception, all parts might not have been executed


Jobs can only be retreived using this API, they can not be
started. Jobs will automatically be started when using for example the
device_syncto API.

List jobs
---------

To fetch information about all jobs:

::

   curl http://hostname/api/v1.0/jobs

The number of jobs to be retreived can be limited by using the
pagination system, like this:

::

   curl http://hostname/api/v1.0/jobs?per_page=50&page=2

The result will look like this:

::

  {
    "status": "success",
    "data": {
        "jobs": [
            {
                "id": "5d0a3d8fdd4287776695dcb6",
                "start_time": "2019-06-19 13:50:08.900000",
                "finish_time": "2019-06-19 13:50:10.151000",
                "status": "FINISHED",
                "function_name": "sync_devices",
                "result": {
                    "eosaccess": [
                        {
                            "name": "push_sync_device",
                            "result": null,
                            "diff": "",
                            "failed": false
                        },
                        {
                            "name": "Generate device config",
                            "result": "hostname eosaccess\n! comment13\nmanagement api http-commands\n no shutdown\nusername admin privilege 15 secret admin\ninterface Management1\n ip address 192.168.50.100/24\n description MGMT\n !\ninterface Ethernet1\n description UPLINK1\n no switchport\n ip address 22.0.0.100/24\n !\ninterface Ethernet2\n description UPLINK2\n no switchport\n ip address 10.0.2.100/24\n !\nntp server 194.58.202.148\nntp server 256.256.256.256\nevent-handler dhclient\n trigger on-boot\n action bash sudo /mnt/flash/initialize_ma1.sh\naaa authorization exec default local",
                            "diff": "",
                            "failed": false
                        },
                        {
                            "name": "Sync device config",
                            "result": null,
                            "diff": "@@ -15,7 +15,7 @@\n !\n no aaa root\n !\n-username admin privilege 15 role network-admin secret sha512 $6$YpD6h6ftCWTo7PZ5$hggo6ine4WxMihdNmwFNqmbuZzxVsms6kBj1Jk5No8nclojXOdpiW6H3U2o8NSpEhnVb7MidOkdNTQ3V1FJVs.\n+username admin privilege 15 role network-admin secret sha512 $6$DW74hZIKavZFaUVh$vvmDARAUOuPNrtRTl5unS0Nax7dyNwLhisVelV8BSEdUplCf8aqhoE6SRoi.fwBzmTKawJ.oa/AKOSYoG5rkq/\n !\n interface Ethernet1\n    description UPLINK1\n@@ -23,7 +23,7 @@\n    ip address 22.0.0.100/24\n !\n interface Ethernet2\n-   description bajs\n+   description UPLINK2\n    no switchport\n    ip address 10.0.2.100/24\n !",
                            "failed": false
                        }
                    ]
                },
                "exception": null,
                "traceback": null,
                "next_job_id": null,
		"finished_devices": [
                    "test_device_1",
                    "test_device_2"
                ]
            }
         ]
      }
   }

The finished_devices attribute will be populated as devices are finishing.
This value will only be updated for every other second to not keep
the database too busy.

Locks
-----

Some jobs running in CNaaS will require a lock to make sure that jobs are not
interfering with each other. For example, only a single syncto job should be
running at the same time or things might break in unexpected ways.
To keep track of who is currently holding the lock for a particular feature
a record is kept in the database. If something unexpected happens this
lock might need to be manually cleared.

List current locks:

::

   curl http://hostname/api/v1.0/joblocks

Manually clear/delete a lock (make sure that no jobs are running first):

::

   curl http://hostname/api/v1.0/joblocks -X DELETE -d '{"name": "devices"}' -H "Content-Type: application/json"
