FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml /app/
COPY requirements.lock /app/
COPY LICENSE /app/
COPY iptv_lan /app/iptv_lan
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps .
ENV PYTHONUNBUFFERED=1
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD ["python", "-m", "iptv_lan.healthcheck"]
CMD ["python", "-m", "iptv_lan.server"]
