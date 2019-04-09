#!/bin/bash

set -e

nginx -c /opt/cnaas/nginx.conf -g "daemon off;"
