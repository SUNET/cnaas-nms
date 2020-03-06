Configuration
=============

Config files
------------

Config files are placed in /etc/cnaas-nms

If you run the docker container version some of these configuration options will
be set by environment variables at startup.

/etc/cnaas-nms/db_config.yml
----------------------------

Defines how to connect to the SQL and redis databases.

/etc/cnaas-nms/api.yml
----------------------

Defines parameters for the API:

- host: Defines the listening host/IP, default 0.0.0.0
- jwtcert: Defines the path to the public JWT certificate used to verify JWT tokens
- httpd_url: URL to the httpd container containing firmware images
- verify_tls: Verify certificate for connections to httpd/firmware server

/etc/cnaas-nms/repository.yml
-----------------------------

Defines paths to git repositories.
