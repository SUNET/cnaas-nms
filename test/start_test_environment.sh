#!/bin/bash

source integrationtests.sh

export COVERAGE=0

#Unset traps
trap - EXIT
trap - ERR

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
	start_docker_environment
	wait_for_api

	echo "Seeding test-environment"

	python3 -c "
from integrationtests import GetTests
tests = GetTests()
tests.test_00_sync()
tests.test_01_init_dist()
	"

	echo "Test environment is now initialized"
fi