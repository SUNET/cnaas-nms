FROM postgres:11

COPY nms.sql /docker-entrypoint-initdb.d/
RUN chown postgres:postgres /docker-entrypoint-initdb.d/*.sql

EXPOSE 5432
