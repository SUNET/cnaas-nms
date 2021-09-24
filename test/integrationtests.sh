#!/bin/bash -e

pushd .
cd ../docker/
# if running selinux on host this is required: chcon -Rt svirt_sandbox_file_t coverage/
mkdir -p coverage/

docker-compose down

if docker volume ls | egrep -q "cnaas-postgres-data$"
then
	if [ -z "$AUTOTEST" ]
	then
		read -p "Do you want to continue and reset existing SQL database? [y/N]" ans
		case $ans in
			[Yy]* ) docker volume rm cnaas-postgres-data;;
			* ) exit 1;;
		esac
	else
		docker volume rm cnaas-postgres-data
	fi
fi

docker volume create cnaas-templates
docker volume create cnaas-settings
docker volume create cnaas-postgres-data
docker volume create cnaas-jwtcert
docker volume create cnaas-cacert

docker-compose -f docker-compose.yaml -f docker-compose.tests.yaml up -d

docker cp ./jwt-cert/public.pem docker_cnaas_api_1:/opt/cnaas/jwtcert/public.pem
docker-compose exec -u root -T cnaas_api /bin/chown -R www-data:www-data /opt/cnaas/jwtcert/
docker-compose exec -u root -T cnaas_api /opt/cnaas/createca.sh

if [ ! -z "$PRE_TEST_SCRIPT" ]
then
	if [ -x "$PRE_TEST_SCRIPT" ]
	then
		echo "Running PRE_TEST_SCRIPT..."
		bash -c $PRE_TEST_SCRIPT
	fi
fi

# go back to test dir
popd

#wait for port 5000
#retry refresh templates 100 times until success

echo "Starting integration tests..."
python3 -m integrationtests

if [ -z "$AUTOTEST" ]
then
	echo "Press enter to continue:"
	read
	echo "Continuing..."
fi

#coverage
# workaround to trigger coverage save
cd ../docker/
# Sleep very long to make sure all napalm jobs are finished?
sleep 120
echo "Gathering coverage reports from integration tests:"
MULE_PID="`docker logs docker_cnaas_api_1 | awk '/spawned uWSGI mule/{print $6}' | egrep -o "[0-9]+" | tail -n1`"
echo "Found mule at pid $MULE_PID"
# Allow for code coverage files to be saved
docker-compose exec -u root -T cnaas_api chown -R www-data:www-data /opt/cnaas/venv/cnaas-nms/src/
docker-compose exec -u root -T cnaas_api kill $MULE_PID
curl -ks -H "Authorization: Bearer $JWT_AUTH_TOKEN" "https://localhost/api/v1.0/system/shutdown" -d "{}" -X POST -H "Content-Type: application/json"
sleep 3

if ls -lh coverage/.coverage-* 2> /dev/null
then
	cp coverage/.coverage-* ../src/
	echo "Starting unit tests..."
	docker-compose exec -T cnaas_api /opt/cnaas/nosetests.sh
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
	if [ -z "$AUTOTEST" ]
	then
		read -p "Do you want to upload coverage report to codecov.io? [y/N]" ans
		case $ans in
			[Yy]* ) bash <(curl -s https://codecov.io/bash);;
			* ) echo "Not uploading coverage report";;
		esac
	else
		bash <(curl -s https://codecov.io/bash)
	fi
	cd ../docker/
else
	echo "ERROR: No coverage data found"
	cd ../
fi

# Change owner back after code coverage is finished
docker-compose exec -u root -T cnaas_api chown -R root:www-data /opt/cnaas/venv/cnaas-nms/src/

docker-compose down
