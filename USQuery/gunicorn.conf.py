"""Gunicorn config, auto-loaded from the working directory by `gunicorn USQuery.wsgi`.

This is what actually drives the production server on render.com (whose start
command is a bare `gunicorn USQuery.wsgi`, so the gunicorn flags in
entrypoint.prod.sh never run there). Keep server tuning here, not in the shell
scripts.

Bill pages do blocking external Congress.gov calls inside the request, so a
single sync worker means one slow upstream stalls the whole app. Use threaded
workers for I/O concurrency and set timeout > the in-request external budget
(see BILL_FETCH_* in app/utils.py) so a slow upstream fails gracefully instead
of tripping a WORKER TIMEOUT. Tune workers to the instance's RAM.
"""

import os

# Render injects $PORT and expects the app to listen on 0.0.0.0:$PORT.
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

worker_class = "gthread"
workers = 2
threads = 4
timeout = 60
graceful_timeout = 30
