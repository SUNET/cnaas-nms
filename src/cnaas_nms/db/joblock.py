import datetime
from typing import Optional, Dict

from sqlalchemy import Column, String, DateTime, Boolean, Integer

import cnaas_nms.db.base
from cnaas_nms.db.session import sqla_session


class JoblockNotFoundError(Exception):
    pass


class Joblock(cnaas_nms.db.base.Base):
    __tablename__ = 'joblock'
    jobid = Column(String(24), unique=True, primary_key=True)  # mongodb ObjectId, 12-byte hex
    name = Column(String(32), unique=True, nullable=False)
    start_time = Column(DateTime, default=datetime.datetime.now)  # onupdate=now
    abort = Column(Boolean, default=False)

    @classmethod
    def aquire_lock(cls, session: sqla_session, name: str, jobid: str) -> bool:
        curlock = session.query(Joblock).filter(Joblock.name == name).one_or_none()
        if curlock:
            return False
        newlock = Joblock(jobid=jobid, name=name, start_time=datetime.datetime.now())
        session.add(newlock)
        session.commit()
        return True

    @classmethod
    def release_lock(cls, session: sqla_session, name: Optional[str] = None,
                     jobid: Optional[str] = None):
        if jobid:
            curlock = session.query(Joblock).filter(Joblock.jobid == jobid).one_or_none()
        elif name:
            curlock = session.query(Joblock).filter(Joblock.name == name).one_or_none()
        else:
            raise ValueError("Either name or jobid must be set to release lock")

        if not curlock:
            raise JoblockNotFoundError("Current lock could not be found")

        session.delete(curlock)
        session.commit()
        return True

    @classmethod
    def get_lock(cls, session: sqla_session, name: Optional[str] = None,
                 jobid: Optional[str] = None) -> Optional[Dict[str, str]]:
        """

        Args:
            session: SQLAlchemy session context manager
            name: name of job/lock
            jobid: jobid

        Returns:
            Dict example: {'name': 'syncto', 'jobid': '5d5aa92dba050d64aa2966dc', 'abort': False}

        """
        if jobid:
            curlock: Joblock = session.query(Joblock).filter(Joblock.jobid == jobid).one_or_none()
        elif name:
            curlock: Joblock = session.query(Joblock).filter(Joblock.name == name).one_or_none()
        else:
            raise ValueError("Either name or jobid must be set to release lock")

        if curlock:
            return {'name': curlock.name, 'jobid': curlock.jobid, 'abort': curlock.abort}
        else:
            return None


