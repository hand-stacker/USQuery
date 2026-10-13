#!/usr/bin/env bash

python manage.py collectstatic --noinput --clear
python manage.py makemigrations
python manage.py migrate --run-syncdb

# Bill pages do blocking external Congress.gov calls inside the request, so a
# single sync worker means one slow upstream stalls the whole app. Use threaded
# workers for I/O concurrency and set --timeout > the in-request external budget
# (see BILL_FETCH_* in app/utils.py) so a slow upstream fails gracefully instead
# of tripping a WORKER TIMEOUT. Tune --workers to the instance's RAM.
python -m gunicorn --bind 0.0.0.0:8000 \
    --worker-class gthread --workers 2 --threads 4 \
    --timeout 60 --graceful-timeout 30 \
    USQuery.wsgi:application