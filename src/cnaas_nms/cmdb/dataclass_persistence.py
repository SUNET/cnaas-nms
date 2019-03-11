
from dataclasses import dataclass, InitVar, fields
from typing import Optional

import datetime

from bson.objectid import ObjectId
import bson.json_util

from cnaas_nms.cmdb.session import mongo_db

@dataclass
class DataclassPersistence:
    id: Optional[ObjectId] = None
    _collection: InitVar[str] = None

    def __post_init__(self, collection):
        if collection:
            self._collection = collection
        else:
            self._collection = self.__class__.__name__

    def from_dict(self, in_dict):
        for field in fields(self):
            if field.name == 'id':
                self.__setattr__('id', in_dict['_id'])
            else:
                if field.name in in_dict:
                    self.__setattr__(field.name, in_dict[field.name])

    def to_dict(self, json_serializable=False):
        ret = {}
        for field in fields(self): 
            field_data = self.__getattribute__(field.name)
            if json_serializable:
                ret[field.name] = self.serialize(field_data)
            else:
                ret[field.name] = field_data
        return ret

    @classmethod
    def serialize(cls, property):
        if isinstance(property, (type(None), str, int)):
            return property
        elif isinstance(property, (ObjectId, datetime.datetime)):
            return str(property)
        elif isinstance(property, dict):
            return property #TODO: recurse?
        else:
            return bson.json_util.dumps(property)

    def create(self):
        with mongo_db() as db:
            collection = db[self._collection]
            self.status = 'scheduled'
            self.id = collection.insert_one({'status':self.status}).inserted_id
            return str(self.id)

    def load(self, id):
        with mongo_db() as db:
            collection = db[self._collection]
            data = collection.find_one({'_id': ObjectId(id)})
            self.from_dict(data)

    def update(self, in_dict):
        update_set = {}
        for k, v in in_dict.items():
            if k in [f.name for f in fields(self)]:
                self.__setattr__(k, v)
                update_set[k] = v
            else:
                print("Unknown field set '{k}' in collection '{self._collection}'")
                update_set[k] = v
        with mongo_db() as db:
            collection = db[self._collection]
            collection.update_one(
                {'_id': self.id},
                {"$set": update_set}
            )
