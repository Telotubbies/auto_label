"""The e2e entrypoint: the real API with deterministic fakes, and a gate no deployment passes.

`playwright.config.ts` starts it with `python -m uvicorn e2e.app:app`. It lives outside the `app`
package on purpose, so no fake module ships in the API image and `app.main` never imports one.
"""
import os

if os.environ.get("LD_E2E") != "1":
    raise RuntimeError("e2e.app is the e2e harness entrypoint; start it with LD_E2E=1")

if os.environ.get("LD_ENV") == "production":
    raise RuntimeError("refusing to start the e2e harness with LD_ENV=production: its workers are "
                       "fakes, so it must never serve a real workspace")

from . import fakes  # noqa: E402  after the gate: a refused start installs nothing

fakes.install()

from app.main import app  # noqa: E402,F401  uvicorn imports this name

__all__ = ["app"]
