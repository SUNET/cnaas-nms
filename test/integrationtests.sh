#!/bin/bash

pushd .
cd ../docker/
# if running selinux on host this is required: chcon -Rt svirt_sandbox_file_t coverage/
mkdir coverage/

export GITREPO_TEMPLATES="git://gitops.sunet.se/cnaas-lab-templates"
export GITREPO_SETTINGS="git://gitops.sunet.se/cnaas-lab-settings"
export GITREPO_ETC="https://github.com/indy-independence/cnaas-nms-lab-etc.git"
export USERNAME_DHCP_BOOT="admin"
export PASSWORD_DHCP_BOOT="abc123abc123"
export USERNAME_DISCOVERED="admin"
export PASSWORD_DISCOVERED="abc123abc123"
export USERNAME_INIT="admin"
export PASSWORD_INIT="abc123abc123"
export USERNAME_MANAGED="admin"
export PASSWORD_MANAGED="abc123abc123"
export COVERAGE=1
export JWT_AUTH_TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiJ9.eyJpYXQiOjE1NzEwNTk2MTgsIm5iZiI6MTU3MTA1OTYxOCwianRpIjoiNTQ2MDk2YTUtZTNmOS00NzFlLWE2NTctZWFlYTZkNzA4NmVhIiwic3ViIjoiYWRtaW4iLCJmcmVzaCI6ZmFsc2UsInR5cGUiOiJhY2Nlc3MifQ.Sfffg9oZg_Kmoq7Oe8IoTcbuagpP6nuUXOQzqJpgDfqDq_GM_4zGzt7XxByD4G0q8g4gZGHQnV14TpDer2hJXw"

docker-compose up -d

# go back to test dir
popd

#wait for port 5000
#retry refresh templates 100 times until success

python3 -m integrationtests

echo "Press any key to continue"
read

#coverage
# workaround to trigger coverage save
cd ../docker/
# Sleep very long to make sure all napalm jobs are finished?
sleep 300
echo "Gathering coverage reports from integration tests:"
docker exec docker_cnaas_api_1 pkill uwsgi
sleep 3

if ls -lh coverage/.coverage-* 2> /dev/null
then
	cp coverage/.coverage-* ../src/
	docker exec docker_cnaas_api_1 /opt/cnaas/nosetests.sh
	echo "Gathering coverage reports from unit tests:"
	ls -lh coverage/.coverage-* 2> /dev/null
	cp coverage/.coverage-nosetests ../src/
	cd ../src/
	source ../../bin/activate
	echo "Try to generate coverage report:"
	coverage combine .coverage-*
	coverage report --omit='*/site-packages/*'
	coverage xml -i --omit='*/site-packages/*,*/templates/*'
	export CODECOV_TOKEN="dbe13a97-70b5-49df-865e-d9b58c4e9742"
	if [ -z "$ASKUPLOAD" ]
	then
		bash <(curl -s https://codecov.io/bash)
	else
		read -p "Do you want to upload coverage report to codecov.io? [y/N]" ans
		case $ans in
			[Yy]* ) bash <(curl -s https://codecov.io/bash);;
			* ) echo "Not uploading coverage report";;
		esac
	fi
	cd ../docker/
else
	echo "ERROR: No coverage data found"
	cd ../
fi

docker-compose down
