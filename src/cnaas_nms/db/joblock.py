import datetime
from typing import Dict, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import relationship

import cnaas_nms.db.base
from cnaas_nms.db.session import sqla_session


class JoblockError(Exception):
    pass


class Joblock(cnaas_nms.db.base.Base):
    __tablename__ = "joblock"
    job_id = Column(Integer, ForeignKey("job.id"), unique=True, primary_key=True)
    job = relationship("Job", foreign_keys=[job_id])
    name = Column(String(32), unique=True, nullable=False)
    start_time = Column(DateTime, default=datetime.datetime.now)  # onupdate=now
    abort = Column(Boolean, default=False)

    def as_dict(self) -> dict:
        """Return JSON serializable dict."""
        d = {}
        for col in self.__table__.columns:
            value = getattr(self, col.name)
            if issubclass(value.__class__, cnaas_nms.db.base.Base):
                continue
            elif issubclass(value.__class__, datetime.datetime):
                value = str(value)
            d[col.name] = value
        return d

    @classmethod
    def acquire_lock(cls, session: sqla_session, name: str, job_id: int) -> bool:
        curlock = session.query(Joblock).filter(Joblock.name == name).one_or_none()
        if curlock:
            return False
        newlock = Joblock(job_id=job_id, name=name, start_time=datetime.datetime.now())
        session.add(newlock)
        session.commit()
        return True

    @classmethod
    def release_lock(cls, session: sqla_session, name: Optional[str] = None, job_id: Optional[int] = None):
        if job_id:
            curlock = session.query(Joblock).filter(Joblock.job_id == job_id).one_or_none()
        elif name:
            curlock = session.query(Joblock).filter(Joblock.name == name).one_or_none()
        else:
            raise ValueError("Either name or job_id must be set to release lock")

        if not curlock:
            raise JoblockError("Current lock could not be found")

        session.delete(curlock)
        session.commit()
        return True

    @classmethod
    def get_lock(
        cls, session: sqla_session, name: Optional[str] = None, job_id: Optional[int] = None
    ) -> Optional[Dict[str, str]]:
        """

        Args:
            session: SQLAlchemy session context manager
            name: name of job/lock
            job_id: job_id

        Returns:
            Dict example: {'name': 'syncto', 'job_id': 3,
            'start_time': '2019-08-23 10:45:07.788892', 'abort': False}

        """
        if job_id:
            curlock: Joblock = session.query(Joblock).filter(Joblock.job_id == job_id).one_or_none()
        elif name:
            curlock: Joblock = session.query(Joblock).filter(Joblock.name == name).one_or_none()
        else:
            raise ValueError("Either name or jobid must be set to release lock")

        if curlock:
            return curlock.as_dict()
        else:
            return None

    @classmethod
    def clear_locks(cls, session: sqla_session):
        """Clear/release all locks in the database."""
        try:
            return session.query(Joblock).delete()
        except DBAPIError as e:
            if e.orig.pgcode == '42P01':
                raise JoblockError("Jobblock table doesn't exist yet, we assume it will be created soon.")
            else:
                raise

