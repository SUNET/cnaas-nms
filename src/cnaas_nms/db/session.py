from contextlib import contextmanager

from redis import StrictRedis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cnaas_nms.app_settings import app_settings

_sessionmaker = None


def _get_session():
    global _sessionmaker
    if _sessionmaker is None:
        conn_str = app_settings.POSTGRES_DSN
        engine = create_engine(conn_str, pool_size=50, max_overflow=50)
        engine.connect()
        _sessionmaker = sessionmaker(bind=engine)
    return _sessionmaker()


@contextmanager
def sqla_session(**kwargs):
    session = _get_session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

@contextmanager
def sqla_test_session(**kwargs):
    session = _get_session()
    try:
        yield session
        session.flush()
    except:
        session.rollback()
        raise
    finally:
        session.close()

@contextmanager
def sqla_execute(**kwargs):
    conn_str = app_settings.POSTGRES_DSN
    engine = create_engine(conn_str)

    with engine.connect() as connection:
        yield connection

@contextmanager
def redis_session(**kwargs):
    with StrictRedis(host=app_settings.REDIS_HOSTNAME, port=app_settings.REDIS_PORT, charset="utf-8", decode_responses=True) as conn:
        yield conn
