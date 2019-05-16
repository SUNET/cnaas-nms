import ipaddress
import datetime
import enum
from ipaddress import IPv4Interface, IPv4Address
from typing import Optional

from sqlalchemy import Column, Integer, Unicode, UniqueConstraint
from sqlalchemy import ForeignKey, Boolean
from sqlalchemy.orm import relationship, load_only
from sqlalchemy_utils import IPAddressType

import cnaas_nms.db.base
import cnaas_nms.db.site
import cnaas_nms.db.device

class User(cnaas_nms.db.base.Base):
    __tablename__ = 'users'
    __table_args__ = (
        None,
        UniqueConstraint('id'),
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    username = Column(Unicode(128))
    password = Column(Unicode(128))
    description = Column(Unicode(255))
    active = Column(Boolean, default=False)
    def as_dict(self):
        """Return JSON serializable dict."""
        d = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if issubclass(value.__class__, enum.Enum):
                value = value.value
            elif issubclass(value.__class__, cnaas_nms.db.base.Base):
                continue
            elif issubclass(value.__class__, ipaddress.IPv4Address):
                value = str(value)
            elif issubclass(value.__class__, datetime.datetime):
                value = str(value)
            d[col.name] = value
        return d

    def get_user(self, username):
        if username in self.as_dict():
            return self.as_dict(['username'])
