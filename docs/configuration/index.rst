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
- verify_tls_device: Verify TLS connections to devices, defaults to True
- cafile: Path to CA certificate used to verify device certificates.
  If no path is specified then the system default CAs will be used.
- cakeyfile: Path to CA key, used to sign device certificates after generation.
- certpath: Path to store generated device certificates in.
- allow_apply_config_liverun: Allow liverun on apply_config API call. Defaults to False.

/etc/cnaas-nms/repository.yml
-----------------------------

Defines paths to git repositories.
