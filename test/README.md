# Integrationtest readme

## Prerequisites

### Install containerlab
Follow the guide found here: https://containerlab.dev/install.

### Install Arista cEOS image
Follow the guide found here https://containerlab.dev/manual/kinds/ceos.

### Install Arista vEOS image (Optional)

*This part can be skipped when running the ceos-only containerlab.*

Follow the guide found here: https://containerlab.dev/manual/kinds/vr-veos and here: https://github.com/srl-labs/vrnetlab/tree/master/arista/veos

With the following modifications:

For the vEOS image you need to modify the start script so it starts in ZTP mode.

First modify the Makefile and swap out the docker-pre-build so it configures a zerotouch-config file with Disabled=False.

```bash
# File: vrnetlab/veos/Makefile
docker-pre-build:
	# checking if ZTP config contains a string (DISABLE=False) in the file /zerotouch-config
	# if it does, we don't need to write this file
	@echo Checking ZTP status
	ZTPOFF=$(shell docker run --rm -it -e LIBGUESTFS_DEBUG=0 -v $$(pwd):/work cmattoon/guestfish --ro -a $(IMAGE) -m /dev/sda2 cat /zerotouch-config 2> /dev/null || echo "false"); \
	echo "$@: ZTPOFF is $$ZTPOFF" && \
	if [ "$$ZTPOFF" != "DISABLE=False" ]; then \
	  echo "Enabling ZTP" && docker run --rm -it -e LIBGUESTFS_DEBUG=0 -v $$(pwd):/work cmattoon/guestfish -a $(IMAGE) -m /dev/sda2 write /zerotouch-config "DISABLE=False"; \
	fi
```

Then modify the docker/launch.py script to not do any initial config.
Just commented out the following lines in the function bootstrap_spin on line 71->76.

```python
# File: vrnetlab/veos/docker/launch.py
# Omitted lines ...
    def bootstrap_spin(self):
# Omitted lines ...
                # self.logger.debug("matched login prompt")
                # self.logger.debug("trying to log in with 'admin'")
                # self.wait_write("admin", wait=None)

                # run main config!
                # self.bootstrap_config()
# Omitted lines ..
```

You can then run make to create the image.  
Follow the README guide to place the vEOS.vmdk in the correct place.

## Run containerlab

### Full containerlab including ztp with veos-image
`sudo containerlab -t cnaas-integration.clab.yml deploy`

### cEOS-only containerlab

This containerlab topology skips the ztp init step and preconfigures the access-switch with the configuration it will have after ztp have completed.

This will complete faster than the full ztp and only needs one type of arista ceos image and needs no nested virtualization.

`sudo containerlab -t cnaas-integration-ceos.clab.yml deploy`

---
If you need to reconfigure the lab from the beginning.  
`sudo containerlab -t cnaas-integration.clab.yml deploy --reconfigure`  
or  
`sudo containerlab -t cnaas-integration-ceos.clab.yml deploy --reconfigure`

Containerlab adds some static routes on the host machine during the test.
- 10.0.6.0/24 mgmt domain
- 192.168.0.0/24 ztp network
- 10.100.3.101/32 eosdist1 mgmt loopback
- 10.100.3.102/32 eosdist2 mgmt loopback

Run containerlab with a specific Arista version by using environment variable: `ARISTA_VERSION`.  
Like:

`sudo ARISTA_VERSION=4.33.6M containerlab -t cnaas-integration.clab.yml deploy`

### Console access

#### vEOS
Console access to vEOS eosaccess-switch.  
`telnet 10.100.2.13 5000`

#### cEOS
Console access to cEOS eosaccess-switch.  
`docker exec -it clab-cnaas-integration-ceos-eosaccess Cli`


## Run integrationtests

Make sure to build production images beforehand.

`docker compose -f docker/docker-compose.yaml build`

Run integrationtests within the test folder.

`./integrationtests.sh`

Run with script to save output to a log-file.

`script -c './integrationtests.sh' out.log`


## Test environment

For local testing and frontend development a full test environment can be setup by using containerlab together with a helper script.

### Start containerlab

`sudo ARISTA_VERSION=4.33.6M containerlab -t cnaas-integration-ceos.clab.yml deploy`

### Initialize the NMS components
`start_test_environment.sh`

### Stop the test environment

`docker compose -f ../docker/docker-compose.yaml down -v`

`sudo ARISTA_VERSION=4.33.6M containerlab -t cnaas-integration-ceos.clab.yml destroy`
