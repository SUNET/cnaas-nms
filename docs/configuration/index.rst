Configuration
=============

CNaaS NMS relies on configuration files and environment variables for configuration.

Config files
------------

Config files are placed in /etc/cnaas-nms


/etc/cnaas-nms/db_config.yml
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Defines how to connect to the SQL and redis databases.

/etc/cnaas-nms/api.yml
^^^^^^^^^^^^^^^^^^^^^^

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
- global_unique_vlans: If True VLAN IDs has to be globally unique, if False
  different DIST switches can reuse same VLAN IDs for different L2 domains.
  Defaults to True.
- init_mgmt_timeout: Timeout to wait for device to apply changed management IP.
  Defaults to 30, specified in seconds (integer).

/etc/cnaas-nms/repository.yml
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Defines paths to git repositories.

.. _configuration_environment_ref:

Environment variables
---------------------

Besides config files, cnaas-nms uses environment variables for configuration.
The environment variables are typically set using docker-compose.

Docker-compose will spin up a multi container environment including the
CNaaS NMS API, httpd and dhcp server, postgresql, redis and the JWT auth server.

There are various ways to set environment variables in docker-compose.
The most common one is the ``docker-compose.yml`` file.

A list of the environment variables used by each Docker container:

cnaas_api

- ``GITREPO_TEMPLATES`` -- templates git repository
- ``GITREPO_SETTINGS`` -- settings git repository
- ``COVERAGE`` -- calculate test coverage. 1 or 0 (yes or no)
- ``USERNAME_DHCP_BOOT`` -- user name to log into devices during DHCP boot process
- ``PASSWORD_DHCP_BOOT``
- ``USERNAME_DISCOVERED`` -- user name for discovered devices
- ``PASSWORD_DISCOVERED``
- ``USERNAME_INIT`` -- user name for initialised devices
- ``PASSWORD_INIT``
- ``USERNAME_MANAGED`` -- user name for managed devices
- ``PASSWORD_MANAGED``
- ``PLUGIN_SETTINGS_FIELDS_MODULE`` - Use a custom module path to override
  settings_fields, defaults to: cnaas_nms.plugins.settings_fields

cnaas_httpd

- ``GITREPO_TEMPLATES`` -- templates git repository

cnaas_dhcpd

- ``GITREPO_ETC`` -- git repository containing dhcpd config
- ``DB_PASSWORD`` -- database password
- ``DB_HOSTNAME`` -- database host
- ``JWT_AUTH_TOKEN`` --  token to authenticate against the cnaas-nms REST API

cnaas_postgres

- ``POSTGRES_USER`` -- database username
- ``POSTGRES_PASSWORD`` -- database password
- ``POSTGRES_DB`` -- name of the cnaas-nms database

Git repository URLs
-------------------

All the options that point to various GIT repositories (``GITREPO_*``) support typical Git-compatible URLs, including,
but not limited to:

- ``ssh://user@host.xz:port/path/to/repo.git/``
- ``https://host.xz/path/to/repo.git/``
- ``git://host.xz/path/to/repo.git/``

Additionally, specific commits or branches can be specified by adding a URL anchor containing a Git reference such as
a branch name, tag or commit ID. Examples:

- ``ssh://user@host.xz:port/path/to/repo.git/#stable``
- ``https://host.xz/path/to/repo.git/#v1.2.3``
- ``git://host.xz/path/to/repo.git/#2a8c7f6c6544dd438808ab1bec560115783a2f2a``
