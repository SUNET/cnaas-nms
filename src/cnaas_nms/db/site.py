from sqlalchemy import Column, Integer, Unicode, UniqueConstraint

import cnaas_nms.db.base


class Site(cnaas_nms.db.base.Base):
    __tablename__ = 'site'
    __table_args__ = (
        None,
        None
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    description = Column(Unicode(255))
