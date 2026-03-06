# Integrationtest readme

## Prerequisites

### Install containerlab
Follow the guide found here: https://containerlab.dev/install.

### Install Arista cEOS image
Follow the guide found here https://containerlab.dev/manual/kinds/ceos.

### Install Arista vEOS image

Follow the guide found here: https://containerlab.dev/manual/kinds/vr-veos and here: https://github.com/srl-labs/vrnetlab/tree/master/arista/veos

With the following modifications:

For the vEOS image you need to modify the start script so it starts in ZTP mode.

First modify the Makefile and swap out the docker-pre-build so it configures a zerotouch-config file with Disabled=False.

```bash
# File: vrnetlab/arista/veos/Makefile
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
# File: vrnetlab/arista/veos/docker/launch.py
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

`sudo containerlab -t cnaas-integration.clab.yml deploy`

If you need to reconfigure the lab from the beginning.  
`sudo containerlab -t cnaas-integration.clab.yml deploy --reconfigure`

Containerlab adds some static routes on the host machine during the test.
- 10.0.6.0/24 mgmt domain
- 192.168.0.0/24 ztp network
- 10.100.3.101/32 eosdist1 mgmt loopback
- 10.100.3.102/32 eosdist2 mgmt loopback

Console access to eosaccess-switch to follow ztp progress.  
`telnet 10.100.2.13 5000`

## Run integrationtests

Make sure to build production images beforehand.

`docker compose -f docker/docker-compose.yaml build`

Run integrationtests within the test folder.

`./integrationtests.sh`
