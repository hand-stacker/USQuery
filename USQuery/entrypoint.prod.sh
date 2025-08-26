#!/usr/bin/env bash

python manage.py collectstatic --noinput
python manage.py makemigrations
python manage.py migrate --run-syncdb

python -m gunicorn --bind 0.0.0.0:8000 --workers 3 USQuery.wsgi:application