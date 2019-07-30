import sys
sys.path.append('src')

from logging.config import fileConfig


from sqlalchemy import engine_from_config
from sqlalchemy import pool
import sqlalchemy_utils

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

from cnaas_nms.db.session import get_sqlalchemy_conn_str
config.set_main_option('sqlalchemy.url', get_sqlalchemy_conn_str())

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from cnaas_nms.db.base import Base
from cnaas_nms.db.device import Device, DeviceType, DeviceState
from cnaas_nms.db.site import Site
from cnaas_nms.db.linknet import Linknet
from cnaas_nms.db.mgmtdomain import Mgmtdomain
from cnaas_nms.db.interface import Interface


target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def include_object(object, name, type_, reflected, compare_to):
    ignore_names = ['apscheduler_jobs']
    if type_ == 'table' and name in ignore_names:
        return False

    return True


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, include_object=include_object,
        literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            include_object=include_object
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
