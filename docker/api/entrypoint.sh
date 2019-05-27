echo ">> Waiting for postgres to start"
WAIT=0
while ! nc -z cnaas_postgres 5432; do
    sleep 1
    WAIT=$(($WAIT + 1))
    if [ "$WAIT" -gt 15 ]; then
        echo "Error: Timeout wating for Postgres to start"
        exit 1
    fi
done

PYTHONPATH=`pwd` python3 cnaas_nms/run.py
