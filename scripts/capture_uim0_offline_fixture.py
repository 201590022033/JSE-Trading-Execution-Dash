"""Capture labelled synthetic or recorded UIM0 baselines without a server.

Requires Python Playwright and an existing Edge installation. All browser
requests are intercepted; unknown requests fail closed. No user database is
opened. Recorded input is supplied separately and never fetched by this script.
Unknown API responses are unavailable; this is not a complete app fixture.
"""
import argparse
import json
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
STAMP = "2026-11-09T12:00:00Z"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--snapshot", type=Path, help="Optional locally recorded MTN responses JSON; never fetched by this script")
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else None
    args.output.mkdir(parents=True, exist_ok=True)
    template = (ROOT / "templates/dashboard.html").read_text(encoding="utf-8")
    template = re.sub(r"\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}", r"/static/\1", template)
    template = template.replace("<body>", '<body><div style="position:fixed;bottom:0;right:0;z-index:99999;background:#ffdb55;color:#111;padding:8px;font-weight:bold">SYNTHETIC OFFLINE FIXTURE — NOT MARKET DATA</div>', 1)
    requests = []

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=str(EDGE), headless=True)
        for case in (("empty", "partial", "stale", "error", "recorded") if snapshot else ("empty", "partial", "stale", "error")):
            for width, height in ((1672, 941), (390, 844)):
                page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                page.clock.install(time="2026-11-09T12:00:00Z")

                def route_request(route):
                    req = route.request
                    url = urlparse(req.url)
                    requests.append({"case": case, "method": req.method, "url": req.url})
                    if url.netloc != "uim0.invalid" or req.method != "GET":
                        return route.abort()
                    if url.path == "/":
                        label = "RECORDED HISTORICAL SNAPSHOT — NOT LIVE" if case == "recorded" else f"SYNTHETIC {case.upper()} FIXTURE — NOT MARKET DATA"
                        return route.fulfill(status=200, content_type="text/html", body=template.replace("SYNTHETIC OFFLINE FIXTURE — NOT MARKET DATA", label))
                    if url.path.startswith("/static/"):
                        path = (ROOT / url.path.lstrip("/")).resolve()
                        if path.is_relative_to(ROOT / "static") and path.is_file():
                            return route.fulfill(status=200, content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", body=path.read_bytes())
                        return route.abort()
                    if case == "recorded" and url.path in snapshot:
                        return route.fulfill(json=snapshot[url.path])
                    if url.path == "/api/v1/strategy-radar/watches" and case != "error":
                        watches = [] if case == "empty" else [{"instrument":"FIXTURE", "pinned":True, "daily":{"sessions":20,"latest_session":"2026-01-01" if case == "stale" else "2026-11-06","coverage":{},"sources":{}},"strategy_id":"synthetic", "strategy_version":"0"}]
                        return route.fulfill(json={"watches":watches,"ranking_receipt":{"source_generated_at":STAMP}})
                    if url.path == "/api/v1/strategy-radar/swing" and case != "error":
                        evaluation = {"strategy_id":"synthetic", "strategy_version":"0", "state":"PARTIAL", "passed":2, "applicable":6, "unknown":4, "evaluated_at":STAMP, "session":"2026-01-01" if case == "stale" else "2026-11-06", "rules":[]}
                        return route.fulfill(json={"evaluations":{"FIXTURE":evaluation}})
                    if case == "stale" and url.path == "/api/v1/strategy-radar/quotes/FIXTURE":
                        return route.fulfill(json={"fields":{"bid":{"selected":None},"ask":{"selected":None},"last":{"selected":{"value":123.45,"kind":"STALE","provider":"SYNTHETIC","source_time":"2026-01-01T12:00:00Z","received_at":"2026-01-01T12:01:00Z","delay_seconds":60}}}})
                    return route.fulfill(status=503, json={"error":"Synthetic fixture: unavailable"})

                page.route("**/*", route_request)
                page.goto("http://uim0.invalid/", wait_until="load")
                if case in ("partial", "stale", "recorded"):
                    page.locator("#radar-points button").first.wait_for(timeout=10000)
                    page.locator("#radar-points button").first.click()
                    if case == "stale":
                        page.locator("#radar-selected-context").get_by_text("STALE", exact=False).wait_for(timeout=10000)
                page.screenshot(path=str(args.output / f"uim0-{case}-{width}.png"), animations="disabled")
                page.close()
        browser.close()
    (args.output / "requests.json").write_text(json.dumps(requests, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
