from sqlalchemy import Column, Integer, Unicode, UniqueConstraint, String
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, backref

import cnaas_nms.db.base


class Stackmember(cnaas_nms.db.base.Base):
    __tablename__ = 'stackmember'
    __table_args__ = (
        UniqueConstraint('device_id', 'member_no'),
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    device_id = Column(Integer, ForeignKey('device.id'), nullable=False)
    device = relationship("Device", foreign_keys=[device_id],
                          backref=backref("Stackmember", cascade="all, delete-orphan"))
    hardware_id = Column(String(64), nullable=False, unique=True)
    member_no = Column(Integer)
    priority = Column(Integer)
