import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from contextlib import contextmanager

def get_sqlalchemy_conn_str(config='/etc/cnaas-nms/db_config.yml'):
    with open(config, 'r') as db_file:
        db_data = yaml.load(db_file)

    conn_str = (
        f"{db_data['type']}://{db_data['username']}:{db_data['password']}@"
        f"{db_data['hostname']}:{db_data['port']}"
    )

    return conn_str

@contextmanager
def session_scope(**kwargs):
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

