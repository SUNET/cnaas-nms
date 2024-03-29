import json
import time
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from cnaas_nms.db.session import redis_session
from cnaas_nms.tools.event import add_event
from cnaas_nms.tools.log import get_logger

REDIS_SYNC_HISTORY_KEYNAME = "sync_history"
logger = get_logger()


class NewSyncEventModel(BaseModel):
    hostname: str
    cause: str
    timestamp: Optional[float] = Field(default_factory=time.time)
    by: str


@dataclass(frozen=True)
class SyncEvent:
    cause: str
    timestamp: float
    by: str
    job_id: Optional[int]


@dataclass
class SyncHistory:
    """Contains a history field which is a dict of hostname: List[SyncEvent]"""

    history: Dict[str, List[SyncEvent]]

    def asdict(self) -> Dict[str, List]:
        return {k: [asdict(e) for e in v] for (k, v) in self.history.items()}

    def redis_dump(self) -> Dict[str, str]:
        # redis doesn't support nested datatypes, so save inner list as string of json instead
        return {k: json.dumps([asdict(e) for e in v]) for (k, v) in self.history.items()}

    def redis_load(self, redis_dict: Dict[str, str]):
        self.history = {k: [SyncEvent(**e) for e in json.loads(v)] for (k, v) in redis_dict.items()}


def add_sync_event(
    hostname: str, cause: str, by: Optional[str] = None, job_id: Optional[int] = None, timestamp: Optional[float] = None
):
    try:
        if not by:
            by = "unknown"
        if not timestamp:
            timestamp = time.time()
        sync_event = SyncEvent(cause, timestamp, by, job_id)
        with redis_session() as redis:
            if not redis.exists(REDIS_SYNC_HISTORY_KEYNAME):
                new_history = SyncHistory(history={hostname: [sync_event]})
                redis.hset(REDIS_SYNC_HISTORY_KEYNAME, mapping=new_history.redis_dump())
                logger.debug("New sync_history hash created in redis")
            else:
                current_sync_event_data = redis.hget(REDIS_SYNC_HISTORY_KEYNAME, hostname)
                current_sync_events: List[SyncEvent] = []
                if current_sync_event_data:
                    current_sync_events = [SyncEvent(**e) for e in json.loads(current_sync_event_data)]
                    current_sync_events.append(sync_event)
                else:
                    current_sync_events = [sync_event]
                json_data = json.dumps([asdict(e) for e in current_sync_events])
                redis.hset(REDIS_SYNC_HISTORY_KEYNAME, key=hostname, value=json_data)
                add_event(
                    event_type="sync",
                    json_data=json.dumps({"syncevent_hostname": hostname, "syncevent_data": asdict(sync_event)}),
                )
    except RedisError as e:
        logger.exception(f"Redis Error while adding sync event (not critical): {e}")
    except Exception as e:
        logger.exception(f"Exception while adding sync event (not critical): {e}")


def get_sync_events(hostnames: Optional[List[str]] = None) -> SyncHistory:
    ret = SyncHistory(history={})
    sync_history = SyncHistory(history={})
    with redis_session() as redis:
        sync_history.redis_load(redis.hgetall(REDIS_SYNC_HISTORY_KEYNAME))
    if hostnames:
        for hostname, events in sync_history.history.items():
            if hostname in hostnames:
                ret.history[hostname] = events
    else:
        ret = sync_history

    return ret


def remove_sync_events(hostname: str):
    with redis_session() as redis:
        redis.hdel(REDIS_SYNC_HISTORY_KEYNAME, hostname)
