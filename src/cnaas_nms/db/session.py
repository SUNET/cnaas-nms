import yaml
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pymongo import MongoClient


def get_dbdata(config='/etc/cnaas-nms/db_config.yml'):
    with open(config, 'r') as db_file:
        return yaml.safe_load(db_file)


def get_sqlalchemy_conn_str(**kwargs) -> str:
    db_data = get_dbdata(**kwargs)

    conn_str = (
        f"{db_data['type']}://{db_data['username']}:{db_data['password']}@"
        f"{db_data['hostname']}:{db_data['port']}/{db_data['database']}"
    )

    return conn_str


@contextmanager
def sqla_session(**kwargs):
    conn_str = get_sqlalchemy_conn_str(**kwargs)

    engine = create_engine(conn_str)
    connection = engine.connect()
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def mongo_db(**kwargs):
    db_data = get_dbdata(**kwargs)
    client = MongoClient(db_data['mongo_hostname'])
    db = client[db_data['database']]
    try:
        yield db
    finally:
        client.close()

