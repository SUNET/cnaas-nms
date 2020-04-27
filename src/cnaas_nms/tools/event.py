from typing import Optional

from cnaas_nms.db.session import redis_session


def add_event(message: str, event_type: str = "log", level: str = "INFO",
              job_id: Optional[int] = None, device_id: Optional[int] = None,
              update_type: Optional[str] = None):
    with redis_session() as redis:
        try:
            data = {"type": event_type, "message": message, "level": level}
            if event_type == "job_id":
                data['job_id'] = job_id
            elif event_type == "device_id":
                data['device_id'] = device_id
            elif event_type == "update":
                data['update_type'] = update_type
            redis.xadd("events",
                       data,
                       maxlen=100)
        except Exception as e:
            pass
