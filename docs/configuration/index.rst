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
- mgmtdomain_reserved_count: Number of IP addresses to reserve for internal use on
  each defined management domain when assigning new management IP addresses to devices.
  Defaults to 5 (e.g. meaning 10.0.0.1 through 10.0.0.5 would remain unassigned on
  a domain for 10.0.0.0/24).
- mgmtdomain_primary_ip_version: For dual stack management domains, this setting
  defines whether IP version 4 or 6 is preferred when an access device's primary
  management address is assigned. The only valid values are therefore 4 and 6.
- commit_confirmed_mode: Integer specifying default commit confirm mode
  (see :ref:`Syncto commit confirm modes<commit_confirm_modes>`). Defaults to 1.
- commit_confirmed_timeout: Time to wait before rolling back an unconfirmed commit,
  specified in seconds. Defaults to 300.
- commit_confirmed_wait: Time to wait between comitting configuration and checking
  that the device is still reachable, specified in seconds. Defaults to 1.

/etc/cnaas-nms/auth_config.yml
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Define parameters for the authentication:

- oidc_conf_well_known_url: OIDC well-known URL for metadata
- oidc_client_secret: The client secret for OIDC
- oidc_client_id: The client_id for OIDC
- oidc_username_attribute: What attribute in access token or userinfo endpoint to use for username, defaults to "email"
- frontend_callback_url: The frontend URL that the OIDC client should redirect to after the login process
- oidc_enabled: Set True to enabled OIDC login. Defaults to False
- audience: The string to verify the aud attribute in the access token with
- verify_audience: Set to False to disable aud check. Defaults to True
- permissions_disabled: set True to disable permissions. Default False

/etc/cnaas-nms/permissions.yml
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Defines permissions levels for users/groups when accessing the API and the frontend. These permissions
are only active when OAuth is enabled.


- config:

  * default_permissions: the name of the role with permissions given to every user by default

- group_mappings:

  * [name_of_token_attribute]: The name of the group or email attribute in the access token, eg "groups" or "email"

    + [value_of_attribute]: Example "admin@example.com" or "admingroup"

      - role: The name of the role to give the user

- roles:

  * [name_of_the_role]:

    + permissions: Each user group can have different sets of permissions for flexibility.
      - methods: HTTP methods on the API, for example, "GET", "POST", "*"
      - endpoints: Uri's of endpoints on the API with possibility to use Glob, for example "/devices", "job**", "/devices/**/interfaces", "*"
      - pages: Pages shown in the menu of the frontend, for example "Devices", "Groups", "*"
      - rights: Actions you can take in the frontend, for example "read", "write", "*"


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
