"""Shared test environment.

The suite logs in once per module, which is more than the 8-per-5-minutes login allowance, so the
in-process rate limiter is off by default. `test_security` turns it on for its own test and restores
this value afterwards.
"""

import os

os.environ.setdefault("LD_RATE_LIMIT", "0")
