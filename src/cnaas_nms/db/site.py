from sqlalchemy import Integer, Unicode
from sqlalchemy.orm import Mapped, mapped_column

import cnaas_nms.db.base


class Site(cnaas_nms.db.base.Base):
    __tablename__ = "site"
    __table_args__ = (None, None)
    id: Mapped[int] = mapped_column(Integer, autoincrement=True, primary_key=True)
    description: Mapped[str] = mapped_column(Unicode(255))
