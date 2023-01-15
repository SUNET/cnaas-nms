FROM postgres:11

ARG SQLFILE=nms.sql

COPY --chown=postgres:postgres ${SQLFILE} /docker-entrypoint-initdb.d/

EXPOSE 5432
