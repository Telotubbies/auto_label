# LabelDesk API — CPU image. Hosted inference + version/export jobs run here;
# GPU training runs on `labeldesk-worker` machines.
FROM python:3.11-slim
ARG TARGETARCH
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LD_DATA_DIR=/data
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN if [ "$TARGETARCH" = "amd64" ]; then pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu; \
    else pip install --no-cache-dir torch torchvision; fi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --system --uid 10001 labeldesk && mkdir -p /data && chown labeldesk /data
USER labeldesk
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')"
# 2 web workers; background jobs run in the separate `worker` service (LD_EMBEDDED_WORKER=0)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
