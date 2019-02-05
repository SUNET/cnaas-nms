from sqlalchemy import Column, Integer, Unicode, UniqueConstraint

import cnaas_nms.cmdb.base

class Site(cnaas_nms.cmdb.base.Base):
    __tablename__ = 'site'
    __table_args__ = (
        None, 
        UniqueConstraint('id')
    )
    id = Column(Integer, autoincrement=True, primary_key=True)
    description = Column(Unicode(255))
