FROM postgres:11

# use for initial db load 
ARG SQLFILE=nms.sql
COPY --chown=postgres:postgres ${SQLFILE} /docker-entrypoint-initdb.d/

EXPOSE 5432
