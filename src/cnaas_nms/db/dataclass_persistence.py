
from dataclasses import dataclass, InitVar, fields
from typing import Optional

import datetime
import enum
import inspect

from bson.objectid import ObjectId
import bson.json_util

from cnaas_nms.db.session import mongo_db
from cnaas_nms.tools.log import get_logger

logger = get_logger()

@dataclass
class DataclassPersistence:
    """Inherit this dataclass to make another dataclass use a persistent datastore backend."""
    id: Optional[ObjectId] = None
    _collection: InitVar[Optional[str]] = None

    def __post_init__(self, collection):
        if collection:
            self._collection = collection
        else:
            self._collection = self.__class__.__name__

    def from_dict(self, in_dict):
        """Populate dataclass fields from given dict."""
        for field in fields(self):
            if field.name == 'id':
                self.__setattr__('id', in_dict['_id'])
            else:
                if field.name in in_dict:
                    if inspect.isclass(field.type) and issubclass(field.type, enum.Enum):
                        self.__setattr__(field.name, field.type(in_dict[field.name]))
                    else:
                        self.__setattr__(field.name, in_dict[field.name])

    def to_dict(self, json_serializable=False):
        """Return dataclass fields as a python dict, optionally only containing
        JSON serializable data."""
        ret = {}
        for field in fields(self): 
            field_data = self.__getattribute__(field.name)
            if json_serializable:
                if inspect.isclass(field.type) and issubclass(field.type, enum.Enum):
                    ret[field.name] = field.type(field_data).name
                else:
                    ret[field.name] = self.serialize(field_data)
            else:
                ret[field.name] = field_data
        return ret

    @classmethod
    def serialize(cls, property):
        """Serialize python objects to JSON compatible data."""
        if isinstance(property, (type(None), str, int)):
            return property
        elif isinstance(property, (ObjectId, datetime.datetime)):
            return str(property)
        elif isinstance(property, dict):
            return property #TODO: recurse?
        else:
            return bson.json_util.dumps(property)

    def create(self, in_dict: dict) -> str:
        """Create an empty record and return the ID."""
        update_set = {}
        for k, v in in_dict.items():
            if isinstance(v, enum.Enum):
                v = v.value
            if k in [f.name for f in fields(self)]:
                self.__setattr__(k, v)
                update_set[k] = v
            else:
                logger.debug(f"Unknown field set '{k}' in collection '{self._collection}'")
                update_set[k] = v
        with mongo_db() as db:
            collection = db[self._collection]
            self.id = collection.insert_one(update_set).inserted_id
            return str(self.id)

    def load(self, id: str):
        """Load data from persistent datastore into the object."""
        in_dict = {}
        with mongo_db() as db:
            collection = db[self._collection]
            data = collection.find_one({'_id': ObjectId(id)})
            # map Enum values back to Enum instances
            for k, v in data.items():
                field_match = [x for x in fields(self) if x.name == k]
                if len(field_match) == 1:
                    field_type = field_match[0].type
                    # TODO: handle Optional[Enum] ?
                    if inspect.isclass(field_type) and issubclass(field_type, enum.Enum):
                        v = field_type(v)
                in_dict[k] = v
            self.from_dict(in_dict)

    def update(self, in_dict: dict):
        """Update object and persistent datastore with fields from in_dict."""
        update_set = {}
        for k, v in in_dict.items():
            if isinstance(v, enum.Enum):
                v = v.value
            if k in [f.name for f in fields(self)]:
                self.__setattr__(k, v)
                update_set[k] = v
            else:
                logger.debug(f"Unknown field set '{k}' in collection '{self._collection}'")
                update_set[k] = v
        with mongo_db() as db:
            collection = db[self._collection]
            collection.update_one(
                {'_id': self.id},
                {"$set": update_set}
            )

    @classmethod
    def get_last_entries(cls, collection_name: str = None, num_entries: int = 10):
        """Get last number of entries from persistent datastore."""
        if not collection_name:
            collection_name = cls.__name__
        with mongo_db() as db:
            collection = db[collection_name]
            return collection.find().sort('_id', -1).limit(num_entries)

