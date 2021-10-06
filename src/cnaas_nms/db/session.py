import os
import yaml
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from cnaas_nms.db.base import Base
from redis import StrictRedis


def get_dbdata(config='/etc/cnaas-nms/db_config.yml'):
    with open(config, 'r') as db_file:
        return yaml.safe_load(db_file)

def get_sqlalchemy_conn_str(**kwargs) -> str:
    db_data = get_dbdata(**kwargs)
    if 'CNAAS_DB_HOSTNAME' in os.environ:
        db_data['hostname'] = os.environ['CNAAS_DB_HOSTNAME']
    if 'CNAAS_DB_PORT' in os.environ:
        db_data['port'] = os.environ['CNAAS_DB_PORT']
    if 'CNAAS_DB_USERNAME' in os.environ:
        db_data['username'] = os.environ['CNAAS_DB_USERNAME']
    if 'CNAAS_DB_PASSWORD' in os.environ:
        db_data['password'] = os.environ['CNAAS_DB_PASSWORD']
    if 'CNAAS_DB_DATABASE' in os.environ:
        db_data['database'] = os.environ['CNAAS_DB_DATABSE']

    return (
        f"{db_data['type']}://{db_data['username']}:{db_data['password']}@"
        f"{db_data['hostname']}:{db_data['port']}/{db_data['database']}"
    )

def create_session():
    conn_str = get_sqlalchemy_conn_str()
    engine = create_engine(conn_str, pool_size=50, max_overflow=50)
    engine.connect()
    Session = sessionmaker(bind=engine)
    return Session()

def create_test_session():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    engine.connect()
    Session = sessionmaker(bind=engine)
    return Session()

@contextmanager
def sqla_session():
    session = create_session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

@contextmanager
def sqla_test_session():
    session = create_test_session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

@contextmanager
def sqla_execute(**kwargs):
    conn_str = get_sqlalchemy_conn_str(**kwargs)
    engine = create_engine(conn_str)

    with engine.connect() as connection:
        yield connection

@contextmanager
def redis_session(**kwargs):
    db_data = get_dbdata(**kwargs)
    with StrictRedis(host=db_data['redis_hostname'], port=6379, charset="utf-8", decode_responses=True) as conn:
        yield conn

