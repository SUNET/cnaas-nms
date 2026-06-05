import json
from datetime import UTC, datetime
from typing import Any, Optional

import requests
from flask import make_response, request
from flask_restx import Namespace, Resource, fields

from cnaas_nms.api.generic import empty_result
from cnaas_nms.app_settings import api_settings
from cnaas_nms.db.device import Device
from cnaas_nms.db.session import sqla_session
from cnaas_nms.db.settings import get_groups
from cnaas_nms.devicehandler.nornir_helper import cnaas_init, inventory_selector
from cnaas_nms.devicehandler.upgradeorder import determine_upgrade_order
from cnaas_nms.scheduler.scheduler import Scheduler
from cnaas_nms.scheduler.wrapper import job_wrapper
from cnaas_nms.tools.log import get_logger
from cnaas_nms.tools.security import get_identity, login_required
from cnaas_nms.version import __api_version__

logger = get_logger()


api = Namespace("firmware", description="API for handling firmwares", prefix="/api/{}".format(__api_version__))

firmware_model = api.model(
    "firmware_download",
    {
        "url": fields.String(required=True),
        "checksum": fields.Nested(
            api.model(
                "firmware_checksum",
                {
                    "algorithm": fields.String(description="checksum algorithm", required=True),
                    "checksum": fields.String(description="checksum value", required=True),
                },
            ),
            required=True,
            description="checksum object containing algorithm and checksum value, if sha1 field is sent instead of checksum object sha1 is assumed as algorithm.",
        ),
        "verify_tls": fields.Boolean(required=False),
        "filename": fields.String(required=True),
    },
)

firmware_upgrade_model = api.model(
    "firmware_upgrade",
    {
        "url": fields.String(required=True),
        "start_at": fields.String(required=False, default=None),
        "download": fields.Boolean(required=False),
        "activate": fields.Boolean(required=False),
        "filename": fields.String(required=False),
        "group": fields.String(required=False),
        "hostname": fields.String(required=False),
        "pre_flight": fields.Boolean(required=False),
        "post_flight": fields.Boolean(required=False, default=False),
        "post_waittime": fields.Integer(required=False, default=600),
        "reboot": fields.Boolean(required=False, default=False),
        "staggered_upgrade": fields.Boolean(required=False, default=False),
    },
)

firmware_upgradecheck_model = api.model(
    "firmware_upgradecheck",
    {"group": fields.String(required=True)},
)


@job_wrapper
def download_firmware_to_nms(**kwargs: dict) -> str:
    try:
        res = requests.post(api_settings.HTTPD_URL, json=kwargs, verify=api_settings.VERIFY_TLS)
        json_data = json.loads(res.content)
    except Exception as e:
        logger.exception(f"Exception while getting firmware: {e}")
        return "Could not download firmware: " + str(e)
    if json_data["status"] == "error":
        return json_data["message"]
    return "File downloaded from: " + str(kwargs["url"])


class FirmwareApi(Resource):
    @login_required
    @api.expect(firmware_model)
    def post(self) -> dict[str, Any]:
        """Download new firmware"""
        json_data = request.get_json()

        kwargs = dict()

        if "url" not in json_data:
            return empty_result(status="error", data="Missing parameter url"), 400

        if "checksum" not in json_data and "sha1" not in json_data:
            return empty_result(status="error", data="Missing parameter checksum"), 400

        if "verify_tls" not in json_data:
            return empty_result(status="error", data="Missing parameter verify_tls"), 400

        kwargs["url"] = json_data["url"]

        # If sha1 is sent use backwards compatible sha1, otherwise use checksum object
        # Will be transformed to a checksum object in HTTPD
        if "sha1" in json_data:
            kwargs["sha1"] = json_data["sha1"]
        else:
            kwargs["checksum"] = json_data["checksum"]

        kwargs["verify_tls"] = json_data["verify_tls"]

        scheduler: Scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            "cnaas_nms.api.firmware:download_firmware_to_nms", when=1, scheduled_by=get_identity(), kwargs=kwargs
        )
        res = empty_result(data="Scheduled job to download firmware")
        res["job_id"] = job_id

        return res

    @login_required
    def get(self) -> dict[str, Any] | tuple[dict[str, Any], int]:
        """Get firmwares"""
        try:
            res = requests.get(api_settings.HTTPD_URL, verify=api_settings.VERIFY_TLS)
            json_data = json.loads(res.content)["data"]
        except Exception as e:
            logger.exception(f"Exception when getting files: {e}")
            return empty_result(status="error", data="Could not get files"), 404
        return empty_result(status="success", data=json_data)


class FirmwareImageApi(Resource):
    @login_required
    def get(self, filename: str) -> dict[str, Any] | tuple[dict[str, Any], int]:
        """Get information about a single firmware"""
        try:
            res = requests.get(f"{api_settings.HTTPD_URL}/{filename}", verify=api_settings.VERIFY_TLS)
            json_data = json.loads(res.content)["data"]
        except Exception as e:
            logger.exception(f"Exception when getting file: {e}")
            return empty_result(status="error", data="Could not get file"), 404
        return empty_result(status="success", data=json_data)

    @login_required
    def delete(self, filename: str) -> dict[str, Any] | tuple[dict[str, Any], int]:
        """Remove firmware"""
        try:
            res = requests.delete(f"{api_settings.HTTPD_URL}/{filename}", verify=api_settings.VERIFY_TLS)
            json_data = json.loads(res.content)["data"]
        except Exception as e:
            logger.exception(f"Exception when deleting file: {e}")
            return empty_result(status="error", data="Could not delete file"), 404
        return empty_result(status="success", data=json_data)


class FirmwareSetDefaultApi(Resource):
    @login_required
    def post(self, filename: str) -> dict[str, Any] | tuple[dict[str, Any], int]:
        """Set a firmware as the default image"""
        try:
            res = requests.post(f"{api_settings.HTTPD_URL}/{filename}/set-default", verify=api_settings.VERIFY_TLS)
            json_data = json.loads(res.content)["data"]
        except Exception as e:
            logger.exception(f"Exception when setting file as default: {e}")
            return empty_result(status="error", data="Could not set file as default"), 404
        return empty_result(status="success", data=json_data)


class FirmwareUpgradeApi(Resource):
    @login_required
    @api.expect(firmware_upgrade_model)
    def post(self):
        """Upgrade firmware on device"""
        json_data = request.get_json()

        kwargs: dict[str, Any] = dict()
        seconds = 1
        date_format = "%Y-%m-%d %H:%M:%S"
        url = api_settings.FIRMWARE_URL

        if "url" not in json_data and url == "":
            return empty_result(
                status="error", data='No external address configured for HTTPD, please specify one with "url"'
            ), 400

        if "url" not in json_data:
            kwargs["url"] = url
        else:
            if isinstance(json_data["url"], str):
                kwargs["url"] = json_data["url"]
            else:
                return empty_result(status="error", data="url should be a string"), 400

        if "activate" in json_data:
            if isinstance(json_data["activate"], bool):
                kwargs["activate"] = json_data["activate"]
            else:
                return empty_result(status="error", data="activate should be a boolean"), 400

        if "download" in json_data:
            if isinstance(json_data["download"], bool):
                kwargs["download"] = json_data["download"]
            else:
                return empty_result(status="error", data="download should be a boolean"), 400

        if "reboot" in json_data:
            if isinstance(json_data["reboot"], bool):
                kwargs["reboot"] = json_data["reboot"]
            else:
                return empty_result(status="error", data="reboot should be a boolean"), 400

        if "pre_flight" in json_data:
            if isinstance(json_data["pre_flight"], bool):
                kwargs["pre_flight"] = json_data["pre_flight"]
            else:
                return empty_result(status="error", data="pre_flight should be a boolean"), 400

        if "post_flight" in json_data:
            if isinstance(json_data["post_flight"], bool):
                kwargs["post_flight"] = json_data["post_flight"]
            else:
                return empty_result(status="error", data="post_flight should be a boolean"), 400

        if "post_waittime" in json_data:
            if isinstance(json_data["post_waittime"], int):
                kwargs["post_waittime"] = json_data["post_waittime"]
            else:
                return empty_result(status="error", data="post_waittime should be an integer"), 400

        if "filename" in json_data:
            if isinstance(json_data["filename"], str):
                kwargs["filename"] = json_data["filename"]
            else:
                return empty_result(status="error", data="filename should be a string"), 400

        total_count: Optional[int] = None
        nr = cnaas_init()

        if "hostname" in json_data:
            hostname = str(json_data["hostname"])
            if not Device.valid_hostname(hostname):
                return empty_result(status="error", data=f"Hostname '{hostname}' is not a valid hostname"), 400
            _, total_count, _ = inventory_selector(nr, hostname=hostname)
            if total_count != 1:
                return (
                    empty_result(status="error", data=f"Hostname '{hostname}' not found or is not a managed device"),
                    400,
                )
            kwargs["hostname"] = hostname
        elif "group" in json_data:
            group_name = str(json_data["group"])
            if group_name not in get_groups():
                return empty_result(status="error", data="Could not find a group with name {}".format(group_name)), 400
            kwargs["group"] = group_name
            _, total_count, _ = inventory_selector(nr, group=group_name)
            kwargs["group"] = group_name
        else:
            return empty_result(status="error", data="No devices to upgrade were specified"), 400

        if "comment" in json_data and isinstance(json_data["comment"], str):
            kwargs["job_comment"] = json_data["comment"]
        if "ticket_ref" in json_data and isinstance(json_data["ticket_ref"], str):
            kwargs["job_ticket_ref"] = json_data["ticket_ref"]

        if "staggered_upgrade" in json_data:
            if isinstance(json_data["staggered_upgrade"], bool):
                kwargs["staggered_upgrade"] = json_data["staggered_upgrade"]
            else:
                return empty_result(status="error", data="staggered_upgrade should be a boolean"), 400

        if "start_at" in json_data:
            try:
                time_start = datetime.strptime(json_data["start_at"], date_format)
                time_now = datetime.now(UTC).replace(tzinfo=None)

                if time_start < time_now:
                    return empty_result(status="error", data="start_at must be in the future"), 400
                time_diff = time_start - time_now
                seconds = int(time_diff.total_seconds())
            except Exception as e:
                logger.exception(f"Exception when scheduling job: {e}")
                return empty_result(status="error", data=f"Invalid date format, should be: {date_format}"), 400

        scheduler: Scheduler = Scheduler()
        job_id = scheduler.add_onetime_job(
            "cnaas_nms.devicehandler.firmware:device_upgrade",
            when=seconds,
            scheduled_by=get_identity(),
            kwargs=kwargs,
        )
        res = empty_result(data="Scheduled job to upgrade devices")
        res["job_id"] = job_id

        resp = make_response(json.dumps(res), 200)
        if total_count:
            resp.headers["X-Total-Count"] = str(total_count)
        resp.headers["Content-Type"] = "application/json"
        return resp


class FirmwareUpgradecheckApi(Resource):
    @login_required
    @api.expect(firmware_upgradecheck_model)
    def post(self):
        """Perform upgrade check on device group"""
        json_data = request.get_json()

        nr = cnaas_init()
        nr_filtered_group, dev_count, _ = inventory_selector(nr, group=json_data["group"])

        device_hostname_list = list(nr_filtered_group.inventory.hosts.keys())

        with sqla_session() as session:  # type: ignore
            upgrade_groups: list[list[str]] = []
            device_list: list[Device] = []

            for device in device_hostname_list:
                dev: Optional[Device] = session.query(Device).filter(Device.hostname == device).one_or_none()
                if not dev:
                    raise Exception("Could not find device: {}".format(device))
                device_list.append(dev)

            try:
                upgrade_device_groups: list[list[Device]] = determine_upgrade_order(session, device_list)
            except NotImplementedError as e:
                return empty_result(status="error", data=str(e)), 400
            except Exception as e:
                return empty_result(status="error", data=f"Could not determine upgrade order: {str(e)}"), 500
            if not upgrade_device_groups:
                return (
                    empty_result(
                        status="error", data="Could not determine upgrade order for the specified device group"
                    ),
                    400,
                )
            upgrade_groups = [[device.hostname for device in group] for group in upgrade_device_groups]

        ret = empty_result(
            status="success",
            data={"upgrade_groups": upgrade_groups, "device_count": dev_count, "steps": len(upgrade_groups)},
        )
        resp = make_response(json.dumps(ret), 200)
        resp.headers["Content-Type"] = "application/json"
        resp.headers["X-Total-Count"] = str(dev_count)
        return resp


# Firmware
api.add_resource(FirmwareApi, "")
api.add_resource(FirmwareImageApi, "/<string:filename>")
api.add_resource(FirmwareSetDefaultApi, "/<string:filename>/set-default")
api.add_resource(FirmwareUpgradeApi, "/upgrade")
api.add_resource(FirmwareUpgradecheckApi, "/upgradecheck")
