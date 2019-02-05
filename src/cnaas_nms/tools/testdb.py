#!/usr/bin/env python3

import yaml

with open('database.yml', 'r') as db_file:
    db_data = yaml.load(db_file)

print(db_data)
conn_str = (
    f"postgresql://{db_data['username']}:{db_data['password']}@"
    f"{db_data['hostname']}:{db_data['port']}"
)

from sqlalchemy import create_engine

engine = create_engine(conn_str)

connection = engine.connect()

from cmdb.site import Site

from sqlalchemy.orm import sessionmaker

Session = sessionmaker(bind=engine)

session = Session()

for site_instance in session.query(Site).order_by(Site.id):
    print(site_instance.id, site_instance.description)

