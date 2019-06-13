Beginner tutorial for CNaaS-NMS
===============================

CNaaS-NMS is a hybrid infrastructure-as-code (IaC) and API driven automation system.
The IaC part is managed by textfiles (YAML, Jinja2) in a version controlled repository (Git),
and the API part is managed using a JSON REST-like API. In this beginner tutorial we will learn
how to manage both parts.

Repositories
------------

There are three main repositories used by each CNaaS-NMS installation:
- templates
- settings
- etc

REST API
--------

The API runs on the container called cnaas/api.

