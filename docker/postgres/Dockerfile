FROM postgres:11

COPY --chown=postgres:postgres nms.sql /docker-entrypoint-initdb.d/

EXPOSE 5432
