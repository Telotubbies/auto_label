# tools/

Development-only utilities — nothing here ships in the product.

- `cdp.py` — Chrome DevTools Protocol driver (list/nav/shot/eval/resize) used to
  capture the Roboflow design reference and to verify local pages headlessly.
  Usage: `CDP_PORT=9223 python tools/cdp.py <list|nav|shot|eval|resize> <target> [args]`
  (Chrome must run with `--remote-debugging-port=9223` and any scratch `--user-data-dir`.)
- `rf/` — sniper JS fragments evaluated through cdp.py to extract computed CSS,
  fonts, and animation specs from reference sites.

Screenshots/tokens produced by these tools live in `design-ref/` (gitignored).
