"""Stdio entry point: `labeldesk-mcp` speaks MCP on stdin/stdout and writes nothing else there."""
from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .api import Api
from .server import build_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="labeldesk-mcp", description="LabelDesk's MCP server, over stdio.")
    parser.add_argument("--url", default=None, help="LabelDesk base URL (default: LABELDESK_URL)")
    parser.add_argument("--api-key", default=None, help="workspace API key (default: LABELDESK_API_KEY)")
    parser.add_argument("--version", action="version", version=f"labeldesk-mcp {__version__}")
    args = parser.parse_args(argv)

    key = args.api_key or os.environ.get("LABELDESK_API_KEY")
    if not key:
        print("LABELDESK_API_KEY is not set", file=sys.stderr)
        raise SystemExit(2)
    api = Api(base_url=args.url)
    api.use(key)
    build_server(api).run("stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
