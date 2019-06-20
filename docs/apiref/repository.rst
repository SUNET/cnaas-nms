Repository
==========

This API can be used to retrevie information about repositorys and also to update them.

It supports GET and PUT.

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
