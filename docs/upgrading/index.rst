Upgrading
=========

When upgrading to a new major version the API will change and expose new URLs using /api/v2.0/
and so on.

When upgrading between minor versions the database schemas might change, use alembic to upgrade.

Micro releases should only contain bug fixes and no changes in features, database schemas etc.
