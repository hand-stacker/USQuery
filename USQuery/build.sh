#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --noinput --clear

python manage.py makemigrations
python manage.py migrate --run-syncdb

