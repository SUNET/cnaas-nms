from sqlalchemy import Column, Integer, UniqueConstraint, String, ForeignKey
from sqlalchemy.orm import relationship

import cnaas_nms.db.base

class Stackmember(cnaas_nms.db.base.Base):
    __tablename__ = 'stackmember'
    __table_args__ = (
        UniqueConstraint('device_id', 'member_no'),
        UniqueConstraint('device_id', 'hardware_id'),
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    device_id = Column(Integer, ForeignKey('device.id'), nullable=False)
    device = relationship("Device", back_populates="stack_members")
    hardware_id = Column(String(64), nullable=False)
    member_no = Column(Integer)
    priority = Column(Integer)

    def as_dict(self) -> dict:
        """Return JSON serializable dict."""
        d = {
            "member_no": self.member_no,
            "hardware_id": self.hardware_id,
            "priority": self.priority,
        }
        return d
