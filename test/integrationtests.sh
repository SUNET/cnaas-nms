#!/bin/bash

pushd .
cd ../docker/

export GITREPO_TEMPLATES="git://gitops.sunet.se/cnaas-lab-templates"
export GITREPO_SETTINGS="git://gitops.sunet.se/cnaas-lab-settings"
export GITREPO_ETC="git://gitops.sunet.se/cnaas-lab-etc"
export COVERAGE=1
docker-compose up -d

popd

#wait for port 5000
#retry refresh templates 100 times until success

python3 -m integrationtests

echo "Press any key to continue"
read

cd ../docker/
docker-compose down

#coverage
