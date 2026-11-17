# LabelDesk's MCP sidecar: the agent endpoint, on the API's network, holding no secret of its own.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The SDK is not on PyPI, so it installs from the build context before the server that imports it.
COPY packages/sdk ./packages/sdk
COPY apps/mcp ./apps/mcp
RUN pip install ./packages/sdk ./apps/mcp \
    && useradd --system --uid 10001 --no-create-home mcp

USER mcp
EXPOSE 8020
CMD ["labeldesk-mcp", "--http", "--host", "0.0.0.0", "--port", "8020"]
