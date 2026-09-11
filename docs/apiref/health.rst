Health
======

Three endpoints report the health of the API, following the
`MicroProfile Health 4.0 <https://download.eclipse.org/microprofile/microprofile-health-4.0/microprofile-health-spec-4.0.html>`_
response format. They require no authentication and are not part of the
versioned API, so a monitor can read them without a token.

Every response carries a ``status`` of ``UP`` or ``DOWN``, and a ``checks``
list holding the individual results. ``UP`` is answered with 200 and ``DOWN``
with 503, so a probe can act on the status code alone.

Liveness
--------

To check that the API is running:

::

   curl https://hostname/api/health/live

This performs no I/O and stays ``UP`` while a dependency is unreachable, so it
is the endpoint to use for a Kubernetes liveness probe or a container health
check. Restarting the API cannot repair a database outage.

Example output:

::

   {
       "status": "UP",
       "checks": []
   }

Readiness
---------

To check that the API can reach the dependencies it needs to answer requests:

::

   curl https://hostname/api/health/ready

PostgreSQL holds the device inventory and job state, and Redis holds the token
cache, event stream and job queue, so the API can serve nothing useful without
either. Use this endpoint for a Kubernetes readiness probe, which takes the pod
out of the Service endpoints while it answers ``DOWN``, and for monitoring.

A result is cached for a few seconds, so probing frequently costs no more than
probing rarely.

Example output:

::

   {
       "status": "UP",
       "checks": [
           {"name": "postgres", "status": "UP"},
           {"name": "redis", "status": "UP"}
       ]
   }

Health
------

To get every check in one call:

::

   curl https://hostname/api/health

Example output when a dependency is unreachable, answered with 503:

::

   {
       "status": "DOWN",
       "checks": [
           {"name": "postgres", "status": "UP"},
           {"name": "redis", "status": "DOWN"}
       ]
   }
