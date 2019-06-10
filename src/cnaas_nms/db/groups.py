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
from cnaas_nms.db.device import Device
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
    def add(cls, name, description=''):
        with sqla_session() as session:
            instance: Groups = session.query(Groups).filter(Groups.name ==
                                                            name).one_or_none()
            if instance is not None:
                return 'Group already exists'
            new_group = Groups()
            new_group.name = name
            new_group.description = description
            session.add(new_group)

    @classmethod
    def get(cls, index=0, name=''):
        result = []
        with sqla_session() as session:
            if index is 0 and name is '':
                instance = session.query(Groups)
            if index != 0:
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
    def update(cls, name='', description=''):
        with sqla_session() as session:
            instance: Groups = session.query(Groups).filter(Groups.name
                                                            == name).one_or_none()
            if instance is None:
                return 'Group not found'
            if name != '':
                instance.name = name
            if description != '':
                instance.description = description
        return None

    @classmethod
    def delete(cls, group_id):
        group = cls.get(index=group_id)
        if group == []:
            return 'Group not found'
        with sqla_session() as session:
            instance: Groups = session.query(Groups).filter(Groups.id
                                                            == group_id).one_or_none()
            session.delete(instance)
            session.commit()
        return


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

    @classmethod
    def add(cls, group_id, device_id):
        with sqla_session() as session:
            groups = session.query(Groups).filter(Groups.id ==
                                                  group_id).one_or_none()
            if not groups:
                return 'Group not found'
            device = session.query(Device).filter(Device.id ==
                                                  device_id).one_or_none()
            if not device:
                return 'Device not found'
            group = groups.as_dict()
            device = device.as_dict()
            device_groups = DeviceGroups()
            device_groups.device_id = device['id']
            device_groups.groups_id = group['id']
            session.add(device_groups)

    @classmethod
    def get(cls, group_id):
        result = []
        with sqla_session() as session:
            for _ in session.query(Device, Groups).filter(DeviceGroups.device_id ==
                                                          Device.id, DeviceGroups.groups_id ==
                                                          Groups.id).filter(Groups.id ==
                                                                            group_id):
                device = dict()
                device['id'] = _.Device.id
                device['hostname'] = _.Device.hostname
                result.append(device)
        return result

    @classmethod
    def delete(cls, group_id, device_id):
        with sqla_session() as session:
            instance: DeviceGroups = session.query(DeviceGroups).filter(DeviceGroups.device_id ==
                                                                        device_id,
                                                                        DeviceGroups.groups_id ==
                                                                        group_id).one_or_none()
            if not instance:
                return 'Couöd not find matching device and group IDs'
            session.delete(instance)
            session.commit()
