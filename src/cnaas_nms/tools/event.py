from typing import Optional

from cnaas_nms.db.session import redis_session


def add_event(
    message: Optional[str] = None,
    event_type: str = "log",
    level: str = "INFO",
    update_type: Optional[str] = None,
    json_data: Optional[str] = None,
):
    with redis_session() as redis:
        try:
            send_data = {"type": event_type, "level": level}
            if event_type == "log":
                send_data["message"] = message
            elif event_type == "update":
                send_data["update_type"] = update_type
                send_data["json"] = json_data
            redis.xadd("events", send_data, maxlen=100)
        except Exception as e:
            print("Error in add_event: {}".format(e))
