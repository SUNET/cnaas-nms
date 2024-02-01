FROM postgres:11

ARG SQLFILE=no-file.*

COPY --chown=postgres:postgres ${SQLFILE} /docker-entrypoint-initdb.d/

EXPOSE 5432
