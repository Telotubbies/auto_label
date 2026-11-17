"""Minimal Chrome DevTools Protocol driver.

Usage:
  py -3.12 cdp.py list                          # list open tabs
  py -3.12 cdp.py nav  <sel> <url>              # navigate tab, wait for load
  py -3.12 cdp.py shot <sel> <out.png> [--full] # screenshot tab
  py -3.12 cdp.py eval <sel> <expr|file.js>     # evaluate JS, print JSON

<sel> = substring of tab url/title, numeric index from `list`, or omitted (first tab).
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

from websocket import create_connection

import os
DEBUG = "http://localhost:" + os.environ.get("CDP_PORT", "9222")


def targets():
    return json.load(urllib.request.urlopen(DEBUG + "/json", timeout=5))


def pick(sel):
    pages = [t for t in targets() if t.get("type") == "page"]
    if not pages:
        sys.exit("no page targets — is Chrome running with --remote-debugging-port=9222?")
    if sel is None:
        return pages[0]
    for t in pages:
        if sel in t.get("url", "") or sel in t.get("title", ""):
            return t
    try:
        return pages[int(sel)]
    except (ValueError, IndexError):
        sys.exit(f"no target matching {sel!r}; run `list`")


class CDP:
    def __init__(self, target):
        self.ws = create_connection(target["webSocketDebuggerUrl"], timeout=60,
                                    suppress_origin=True)
        self._id = 0

    def cmd(self, method, **params):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    sys.exit(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def eval(self, expr):
        r = self.cmd("Runtime.evaluate", expression=expr, returnByValue=True,
                     awaitPromise=True)
        if r.get("exceptionDetails"):
            sys.exit(json.dumps(r["exceptionDetails"], indent=2)[:2000])
        return r.get("result", {}).get("value")


def wait_ready(cdp, timeout=20):
    for _ in range(timeout * 2):
        if cdp.eval("document.readyState") == "complete":
            return
        time.sleep(0.5)
    sys.exit("page did not finish loading")


def main():
    args = sys.argv[1:]
    if not args or args[0] == "list":
        for i, t in enumerate(targets()):
            if t.get("type") == "page":
                print(f"[{i}] {t.get('title', '')[:60]}\n    {t.get('url', '')}")
        return

    op = args[0]
    sel = None if len(args) < 2 else args[1]
    cdp = CDP(pick(sel))

    if op == "nav":
        cdp.cmd("Page.enable")
        cdp.cmd("Page.navigate", url=args[2])
        wait_ready(cdp)
        print(cdp.eval("location.href"))
    elif op == "shot":
        full = "--full" in args
        out = Path(args[2])
        params = {"format": "png", "captureBeyondViewport": full}
        if full:
            m = cdp.cmd("Page.getLayoutMetrics")
            cs = m["cssContentSize"]
            params["clip"] = {"x": 0, "y": 0, "width": cs["width"],
                              "height": cs["height"], "scale": 1}
        data = cdp.cmd("Page.captureScreenshot", **params)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(__import__("base64").b64decode(data["data"]))
        print(out.resolve())
    elif op == "eval":
        src = args[2]
        p = Path(src)
        if p.suffix == ".js" and p.is_file():
            src = p.read_text(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(cdp.eval(src), ensure_ascii=False, indent=2))
    elif op == "resize":
        w, h = int(args[2]), int(args[3])
        mobile = "--mobile" in args
        cdp.cmd("Emulation.setDeviceMetricsOverride", width=w, height=h,
                deviceScaleFactor=1, mobile=mobile)
        time.sleep(1.5)
        print(cdp.eval("JSON.stringify({w: innerWidth, h: innerHeight})"))
    elif op == "click":
        # click <sel-tab> <x> <y>
        x, y = float(args[2]), float(args[3])
        for t in ("mousePressed", "mouseReleased"):
            cdp.cmd("Input.dispatchMouseEvent", type=t, x=x, y=y,
                    button="left", clickCount=1)
        print("clicked", x, y)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
