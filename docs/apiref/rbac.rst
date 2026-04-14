RBAC
====

The RBAC (Role-Based Access Control) API is used to manage roles, role mappings
and role permissions. Roles define a named set of permissions, role mappings
associate user attributes (from OIDC claims) with roles, and role permissions
specify which API endpoints and HTTP methods a role is allowed to access.

RBAC can be configured either via the :ref:`permissions.yml <etc-cnaas-nms-permissions-yml>`
file or via the database using this API. Permissions from both sources are
combined at runtime.

Roles
-----

Show roles
^^^^^^^^^^

To list all roles:

::

   curl https://hostname/api/v1.0/rbac/roles

This returns roles from both permissions.yml and the database:

::

   {
       "status": "success",
       "data": [
           {
               "id": 3217498765,
               "name": "admin",
               "description": "from permissions.yml"
           },
           {
               "id": 1,
               "name": "operator",
               "description": "Network operators"
           }
       ]
   }

Create role
^^^^^^^^^^^

To create a new role:

::

   curl -H "Content-Type: application/json" -X POST -d
   '{"name": "operator", "description": "Network operators"}'
   https://hostname/api/v1.0/rbac/roles

The JSON structure should have the following fields:

   * name (mandatory): Unique role name
   * description (optional): Human-readable description

Delete role
^^^^^^^^^^^

To delete a role by ID:

::

   curl -X DELETE https://hostname/api/v1.0/rbac/roles/1


Role mappings
-------------

Role mappings associate user attributes from OIDC token claims with roles.
When a user authenticates, their token claims are compared against the
configured mappings to determine which roles they are assigned.

Show role mappings
^^^^^^^^^^^^^^^^^^

To list all role mappings:

::

   curl https://hostname/api/v1.0/rbac/role_mappings

Example output:

::

   {
       "status": "success",
       "data": [
           {
               "id": 1,
               "attribute_name": "email",
               "attribute_value": "admin@example.com",
               "role_id": 1,
               "last_modified_by": "admin",
               "last_modified": "2025-01-15T10:30:00"
           }
       ]
   }

Create role mapping
^^^^^^^^^^^^^^^^^^^

To create a new role mapping:

::

   curl -H "Content-Type: application/json" -X POST -d
   '{"attribute_name": "email", "attribute_value": "admin@example.com", "role_id": 1}'
   https://hostname/api/v1.0/rbac/role_mappings

The JSON structure should have the following fields:

   * attribute_name (mandatory): The OIDC claim name to match (e.g. "email", "sub", "preferred_username")
   * attribute_value (mandatory): The value to match against
   * role_id (mandatory): The ID of the role to assign when matched

Delete role mapping
^^^^^^^^^^^^^^^^^^^

To delete a role mapping by ID:

::

   curl -X DELETE https://hostname/api/v1.0/rbac/role_mappings/1


Role permissions
----------------

Role permissions define what API endpoints and HTTP methods a role is allowed
to access. Each permission entry specifies a set of endpoint patterns and
methods. Optionally, exclude_endpoints can be used to deny specific endpoints
that would otherwise be matched by a wildcard in endpoints.

Show role permissions
^^^^^^^^^^^^^^^^^^^^^

To list all role permissions:

::

   curl https://hostname/api/v1.0/rbac/role_permissions

Example output:

::

   {
       "status": "success",
       "data": [
           {
               "id": 1,
               "role_id": 1,
               "methods": ["GET", "POST"],
               "endpoints": ["/device/**"],
               "exclude_endpoints": ["/device/core*/**"],
               "pages": ["Devices", "Groups"],
               "rights": ["read", "write"],
               "last_modified_by": "admin",
               "last_modified": "2025-01-15T10:30:00"
           }
       ]
   }

Create role permission
^^^^^^^^^^^^^^^^^^^^^^

To create a new role permission:

::

   curl -H "Content-Type: application/json" -X POST -d
   '{"role_id": 1, "methods": ["GET"], "endpoints": ["/**"], "exclude_endpoints": ["/rbac/**"]}'
   https://hostname/api/v1.0/rbac/role_permissions

The JSON structure should have the following fields:

   * role_id (mandatory): The ID of the role this permission belongs to
   * methods (mandatory): List of allowed HTTP methods. Use ``["*"]`` to allow all methods
   * endpoints (mandatory): List of allowed endpoint patterns (see Endpoint patterns below)
   * exclude_endpoints (optional): List of endpoint patterns to exclude from the allowed set
   * pages (optional): List of WebUI pages the role can access
   * rights (optional): List of WebUI rights (e.g. "read", "write")

Update role permission
^^^^^^^^^^^^^^^^^^^^^^

To update an existing role permission by ID:

::

   curl -H "Content-Type: application/json" -X PUT -d
   '{"role_id": 1, "methods": ["GET", "POST"], "endpoints": ["/**"], "exclude_endpoints": ["/rbac/**", "/system/**"]}'
   https://hostname/api/v1.0/rbac/role_permissions/1

Delete role permission
^^^^^^^^^^^^^^^^^^^^^^

To delete a role permission by ID:

::

   curl -X DELETE https://hostname/api/v1.0/rbac/role_permissions/1


Endpoint patterns
-----------------

Endpoint patterns use Unix shell-style wildcards (fnmatch). The patterns are
matched against the request URI with the ``/api/v1.0`` prefix and query string
removed. For example, a request to ``/api/v1.0/device/myhost?per_page=50`` is
matched against ``/device/myhost``.

Available patterns:

   * ``*`` (bare, as the only entry): Matches all endpoints
   * ``/devices``: Exact match
   * ``/device/*``: Matches a single path segment (e.g. ``/device/myhost`` but not ``/device/myhost/interfaces``)
   * ``/device/**``: Matches any number of path segments (e.g. ``/device/myhost/interfaces``)
   * ``/device/**/interfaces``: Matches nested paths ending with ``/interfaces``

Exclude endpoints
^^^^^^^^^^^^^^^^^

The ``exclude_endpoints`` field uses the same pattern syntax as ``endpoints``.
When a request matches both an endpoint pattern and an exclude pattern within
the same permission entry, the request is denied by that entry. However, another
permission entry for the same user can still independently grant access.

This is useful for granting broad access with specific exceptions. For example,
to allow a role access to all endpoints except RBAC management:

::

   {
       "methods": ["*"],
       "endpoints": ["*"],
       "exclude_endpoints": ["/rbac/**"]
   }
