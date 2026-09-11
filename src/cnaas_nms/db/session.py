from collections.abc import Generator
from contextlib import contextmanager

from redis import StrictRedis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from cnaas_nms.app_settings import app_settings

_sessionmaker = None

# Bound the wait for an unreachable dependency, so a request fails instead of
# occupying a worker until the OS gives up on the TCP connection.
CONNECT_TIMEOUT = 5


def _get_session():
    global _sessionmaker
    if _sessionmaker is None:
        conn_str = app_settings.POSTGRES_DSN
        engine = create_engine(
            conn_str, pool_size=50, max_overflow=50, connect_args={"connect_timeout": CONNECT_TIMEOUT}
        )
        engine.connect()
        _sessionmaker = sessionmaker(bind=engine)
    return _sessionmaker()


@contextmanager
def sqla_session(**kwargs) -> Generator[Session, None, None]:
    session = _get_session()
    try:
        yield session
        session.commit()
    except Exception:  # noqa: S110
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
    with StrictRedis(
        host=app_settings.REDIS_HOSTNAME,
        port=app_settings.REDIS_PORT,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=CONNECT_TIMEOUT,
        socket_timeout=CONNECT_TIMEOUT,
    ) as conn:
        yield conn
