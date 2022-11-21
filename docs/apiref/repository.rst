Repository
==========

This API can be used to retrevie information about repositories and also to update them.

It supports GET and PUT operations on /settings and /templates paths.

Get repository information
--------------------------

To get information about the last change to a repository we can use CURL:

::

   curl -X GET http://hostname/api/v1.0/repository/settings

This will return information about who did the last commit to this repository:

::

   {
    "status": "success",
    "data": "Commit cdf978245c3782ec391ffa2bda3ca540577ad36f master by Kristofer Hallin at 2019-06-13 10:07:32+02:00\n"
   }


Refresh repository
------------------

To refresh the contents of a repository we can use a PUT request. CNaaS will then update the corresponding Git repository.

::

   curl -H "Content-Type: application/json" -X PUT http://hostname/api/v1.0/repository/settings -d '{"action": "REFRESH"}'

We should then get a response back stating the last commit that was done:

::

   {
    "status": "success",
    "data": "Commit cdf978245c3782ec391ffa2bda3ca540577ad36f master by Kristofer Hallin at 2019-06-13 10:07:32+02:00\n"
   }

If it's the first time you refresh the repository or if the configured URL to the repository
changes you will get a message saying "Cloned new from remote."

If an error was detected in the settings repository you will get a response like this:

::

   {
     "status": "error",
     "message": "Syntax error in repository: Validation error for setting vxlans->student2->vlan_id, bad value: 501555 (value origin: global->vxlans.yml)\nMessage: ensure this value is less than 4096\n"
   }

The last commit to the settings repository that did not encounter any errors will be
cached and used instead of a commit with errors. This cache is cleared if redis is
restarted.