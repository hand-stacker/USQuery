FROM python:3.11-slim AS builder

RUN mkdir /app
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY requirements.txt /app/

RUN pip install --upgrade pip && \
	apt-get update && \
	apt-get install gcc libpq-dev -y && \
	pip install --no-cache-dir -r requirements.txt && \
	apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
	pip cache purge

# stage 2 : production stage
FROM python:3.11-slim
RUN apt-get update &&\
	apt-get install gcc libpq-dev -y && \
	useradd -m -r appuser && \
	mkdir /app && \
	chown -R appuser /app

COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

WORKDIR /app

COPY --chown=appuser:appuser . .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

USER appuser
EXPOSE 8000
RUN chmod +x /app/entrypoint.prod.sh

CMD ["/app/entrypoint.prod.sh"]