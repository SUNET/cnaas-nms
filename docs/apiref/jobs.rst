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
          "id": 101,
          "status": "FINISHED",
          "scheduled_time": "2019-12-05T13:06:03.319761",
          "start_time": "2019-12-05T13:06:03.375200",
          "finish_time": "2019-12-05T13:06:05.775562",
          "function_name": "sync_devices",
          "scheduled_by": null,
          "comment": null,
          "ticket_ref": null,
          "next_job_id": null,
          "result": {
            "devices": {
              "eosdist": {
                "failed": false,
                "job_tasks": [
                  {
                    "diff": "",
                    "failed": false,
                    "result": null,
                    "task_name": "push_sync_device"
                  },
                  {
                    "diff": "",
                    "failed": false,
                    "result": "hostname eosdist\n...",
                    "task_name": "Generate device config"
                  },
                  {
                    "diff": "@@ -16,8 +16,6 @@\n +hostname eosdist\n...",
                    "failed": false,
                    "result": null,
                    "task_name": "Sync device config"
                  }
                ]
              }
            }
          },
          "exception": null,
          "finished_devices": [
            "eosdist"
          ],
          "change_score": 21
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
