# LabelDesk inference — CPU image (ONNX Runtime). No torch, no secrets, non-root.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LD_INFERENCE_MODELS=/models

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py detect.py ./

RUN useradd --system --uid 10001 --create-home inference \
    && mkdir -p /models && chown inference:inference /models
USER inference

VOLUME ["/models"]
EXPOSE 8010
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8010/healthz')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
