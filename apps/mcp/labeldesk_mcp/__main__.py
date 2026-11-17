"""Entry point: MCP over stdio by default, or one authenticated HTTP endpoint with `--http`."""
from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .api import Api
from .http import build_app
from .server import build_server


def _comma_list(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="labeldesk-mcp", description="LabelDesk's MCP server.")
    parser.add_argument("--url", default=None, help="LabelDesk base URL (default: LABELDESK_URL)")
    parser.add_argument("--api-key", default=None, help="workspace API key (default: LABELDESK_API_KEY)")
    parser.add_argument("--http", action="store_true", help="serve Streamable HTTP on /mcp, keyed per request")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8020, help="HTTP port (default: 8020)")
    parser.add_argument("--version", action="version", version=f"labeldesk-mcp {__version__}")
    args = parser.parse_args(argv)

    api = Api(base_url=args.url)
    if args.http:
        import uvicorn

        app = build_app(build_server(api), api,
                        allowed_hosts=_comma_list("LD_MCP_ALLOWED_HOSTS"),
                        allowed_origins=_comma_list("LD_MCP_ALLOWED_ORIGINS"))
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    key = args.api_key or os.environ.get("LABELDESK_API_KEY")
    if not key:
        print("LABELDESK_API_KEY is not set", file=sys.stderr)
        raise SystemExit(2)
    api.use(key)
    build_server(api).run("stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
