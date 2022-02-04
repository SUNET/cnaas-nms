from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import backref, relationship

import cnaas_nms.db.base


class Stackmember(cnaas_nms.db.base.Base):
    __tablename__ = 'stackmember'
    __table_args__ = (
        UniqueConstraint('device_id', 'member_no'),
        UniqueConstraint('device_id', 'hardware_id'),
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    device_id = Column(Integer, ForeignKey('device.id'), nullable=False)
    device = relationship("Device", foreign_keys=[device_id],
                          backref=backref("Stackmember", cascade="all, delete-orphan"))
    hardware_id = Column(String(64), nullable=False)
    member_no = Column(Integer)
    priority = Column(Integer)
