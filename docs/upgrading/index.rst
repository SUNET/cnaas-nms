Upgrading
=========

Versioning schema based on Python PEP 440, <major>.<minor>.<micro> (ex 1.0.0)

When upgrading to a new major version the API will change and expose new URLs using /api/v2.0/
and so on.

When upgrading between minor versions the database schemas might change, use alembic to upgrade.
Also settings options/template variables might change between minor versions.

Micro releases should only contain bug fixes and no changes in features or database schemas.
