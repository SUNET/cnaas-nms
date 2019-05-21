from __future__ import annotations

import ipaddress
import datetime
import enum
import re
from typing import Optional, List

from sqlalchemy import Column, Integer, Unicode, String, UniqueConstraint
from sqlalchemy import Enum, DateTime, Boolean
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy_utils import IPAddressType

from cnaas_nms.db.session import sqla_session
from cnaas_nms.api.generic import build_filter, empty_result

import cnaas_nms.db.base


class Groups(cnaas_nms.db.base.Base):
    __tablename__ = 'groups'
    __table_args__ = (
        None,
        UniqueConstraint('name'),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    name = Column(Unicode(255), nullable=False)
    description = Column(Unicode(255))

    def as_dict(self) -> dict:
        """Return JSON serializable dict."""
        d = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if issubclass(value.__class__, enum.Enum):
                value = value.name
            elif issubclass(value.__class__, cnaas_nms.db.base.Base):
                continue
            elif issubclass(value.__class__, ipaddress.IPv4Address):
                value = str(value)
            elif issubclass(value.__class__, datetime.datetime):
                value = str(value)
            d[col.name] = value
        return d

    @classmethod
    def group_add(cls, name, description=''):
        retval = []
        with sqla_session() as session:
            instance: Groups = session.query(Groups).filter(Groups.name ==
                                                            name).one_or_none()
            if instance is not None:
                retval.append('Group already exists')
                return retval
            new_group = Groups()
            new_group.name = name
            new_group.description = description
            session.add(new_group)
        return retval

    @classmethod
    def group_get(cls, index=0, name=''):
        result = []
        with sqla_session() as session:
            if index is 0 and name is '':
                instance = session.query(Groups)
                instance = build_filter(Groups, instance)
            if index != 0:
                print(index)
                instance: Groups = session.query(Groups).filter(Groups.id ==
                                                                index).one_or_none()
            elif name is not '':
                instance: Groups = session.query(Groups).filter(Groups.name ==
                                                                name).one_or_none()
            if instance is None:
                return result
            if isinstance(instance, Groups):
                result.append(instance.as_dict())
            else:
                for _ in instance:
                    result.append(_.as_dict())
        return result

    @classmethod
    def group_update(cls, name='', description=''):
<<<<<<< HEAD
=======
        retval = []
>>>>>>> 91bd4ef679fa7f8bd8258ab81082c842a78af49b
        with sqla_session() as session:
            instance: Groups = session.query(Groups).filter(Groups.name
                                                            == name).one_or_none()
            if instance is None:
<<<<<<< HEAD
                return 'Group not found'
=======
                retval = 'Group not found'
                return retval
>>>>>>> 91bd4ef679fa7f8bd8258ab81082c842a78af49b
            if name != '':
                instance.name = name
            if description != '':
                instance.description = description
<<<<<<< HEAD
        return None
=======
        return retval
>>>>>>> 91bd4ef679fa7f8bd8258ab81082c842a78af49b


class DeviceGroups(cnaas_nms.db.base.Base):
    __tablename__ = 'device_groups'
    __table_args__ = (
        None,
        UniqueConstraint('id'),
    )

    id = Column(Integer, autoincrement=True, primary_key=True)
    groups_id = Column(Integer, ForeignKey('groups.id'))
    device_id = Column(Integer, ForeignKey('device.id'))

    def as_dict(self) -> dict:
        """Return JSON serializable dict."""
        d = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if issubclass(value.__class__, enum.Enum):
                value = value.name
            elif issubclass(value.__class__, cnaas_nms.db.base.Base):
                continue
            elif issubclass(value.__class__, ipaddress.IPv4Address):
                value = str(value)
            elif issubclass(value.__class__, datetime.datetime):
                value = str(value)
            d[col.name] = value
        return d
