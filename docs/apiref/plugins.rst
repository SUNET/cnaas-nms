Plugins
=======

This API can be used to retrevie information about what plugins are currently used.

It supports GET and PUT.

Get repository information
--------------------------

To get information about currently loaded plugins and available plugin variables:

::

   curl -X GET http://hostname/api/v1.0/plugins

Example output:

::

  {
      "status": "success",
      "data": {
          "loaded_plugins": [
              "cnaas_nms.plugins.filewriter"
          ],
          "plugindata": {
              "plugins": [
                  {
                      "filename": "filewriter.py",
                      "vars": {
                          "logfile": "/tmp/filewriter.log"
                      }
                  }
              ]
          }
      }
  }


Run plugin selftests
--------------------

Plugins can define a selftest function to test that it can access it's system API etc.
This can be tested by calling PUT on the plugins url.

::

   curl -H "Content-Type: application/json" -X PUT http://hostname/api/v1.0/plugins -d '{"action": "selftest"}'

We should then get a response back with a list of return values:

::

  {
      "status": "success",
      "data": {
          "result": [
              true
          ]
      }
  }
