from typing import Optional

from cnaas_nms.db.session import redis_session


def add_event(
    message: Optional[str] = None,
    event_type: str = "log",
    level: str = "INFO",
    update_type: Optional[str] = None,
    json_data: Optional[str] = None,
):
    """

    Args:
        message: used for type "log", string with log message
        event_type: Can be one of "log", "update" or "sync"
        level:
        update_type:
        json_data: used with "update" or "sync", contains updated object or sync event

    Returns:

    """
    with redis_session() as redis:
        try:
            send_data = {"type": event_type, "level": level}
            if event_type == "log":
                send_data["message"] = message
            elif event_type == "update":
                send_data["update_type"] = update_type
                send_data["json"] = json_data
            elif event_type == "sync":
                send_data["json"] = json_data
            redis.xadd("events", send_data, maxlen=100)
        except Exception as e:
            print("Error in add_event: {}".format(e))
