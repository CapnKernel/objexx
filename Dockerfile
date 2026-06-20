FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=conf.settings

WORKDIR /app

COPY src/requirements.txt .
RUN apt-get update && \
    apt-get install -y --no-install-recommends uwsgi uwsgi-plugin-python3 && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /var/lib/apt/lists/*

COPY src/ .

# Generate production local_settings.py from docker_settings.py
# settings.py imports local_settings.py at the bottom, so this
# makes all production overrides take effect automatically.
COPY src/conf/docker_settings.py conf/local_settings.py

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

RUN useradd -u 1120 -m user && \
    chown -R user:user /app && \
    mkdir -p /app/static /data/db /data/media /data/env && \
    chown -R user:user /data /app/static
USER user

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
