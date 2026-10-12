"""Private weekly import and bounded daily local Ollama cross-source research."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(env, *, brief_file=None, edition_date=None, retry_failed=False, local=False):
    import requests
    from market_intelligence.weekly_brief import local_scan, normalize_items, response_schema, bounded_scan_input
    from application.opportunities.public_research import public_share_catalog
    from sentiment_providers import SentimentProviders
    now = datetime.now(timezone.utc)
    url, token = env.get("SWING_RESEARCH_URL", ""), env.get("SWING_DATA_UPLOAD_TOKEN", "")
    if local:
        url = "http://127.0.0.1:5000"
    if (not local and urlparse(url).scheme != "https") or not token:
        raise ValueError("Private HTTPS upload configuration required")
    base = url.rstrip("/") + "/api/market-intelligence/weekly-brief"
    headers = {"Authorization": "Bearer "+token}
    folder = ROOT / "runtime" / "weekly-news-research"
    folder.mkdir(parents=True, exist_ok=True)
    if brief_file:
        response = requests.post(base+"/import", json={"text": Path(brief_file).read_text(encoding="utf-8-sig"),
                                 "edition_date": edition_date}, headers=headers, timeout=30, allow_redirects=False)
        if response.status_code != 202:
            return {"state": "IMPORT_FAILED", "http_status": response.status_code}
        brief = response.json()
        (folder / (brief["brief_id"]+".json")).write_text(json.dumps(brief), encoding="utf-8")
        return {"state": "WEEKLY_BRIEF_IMPORTED", "edition_date": brief["edition_date"]}
    response = requests.get(base, timeout=30, allow_redirects=False)
    response.raise_for_status()
    state = response.json()
    if not state.get("enabled"):
        return {"state": "WEEKLY_RESEARCH_DISABLED"}
    briefs = state.get("briefs", [])
    if not briefs:
        return {"state": "WAITING_FOR_WEEKLY_BRIEF"}
    brief = max(briefs, key=lambda b: (b["edition_date"], b["received_at"]))
    if now.date()-datetime.fromisoformat(brief["edition_date"]).date() > timedelta(days=14):
        return {"state": "WAITING_FOR_FRESH_WEEKLY_BRIEF"}
    # One durable attempt per UTC day. Completed outbox retries need no model.
    outbox = folder / (now.date().isoformat()+"-outbox.json")
    receipt = folder / (now.date().isoformat()+"-attempt.json")
    if outbox.exists():
        payload = json.loads(outbox.read_text(encoding="utf-8"))
    else:
        attempts = json.loads(receipt.read_text(encoding="utf-8")).get("attempts", 1) if receipt.exists() else 0
        if receipt.exists() and (not retry_failed or attempts >= 5):
            return {"state": "LOCAL_DAILY_MODEL_BUDGET_ALREADY_USED"}
        feed = requests.get(url.rstrip("/")+"/api/feed/news", timeout=30, allow_redirects=False)
        feed.raise_for_status()
        items = (feed.json().get("data") or {}).get("items", [])
        scan_brief, items, prior, coverage = bounded_scan_input(brief, items, state.get("previous_week"), now, public_share_catalog())
        provider = SentimentProviders(environ=env)
        local = provider.providers[0]
        local.model = env.get("WEEKLY_NEWS_OLLAMA_MODEL") or local.model
        provider._local_options = {"num_ctx": 8192, "num_predict": 400, "temperature": 0, "num_gpu": 0,
                                   **provider._local_options, "num_predict": 400}
        charts_path = ROOT / "runtime" / "local-swing-data" / "latest.json"
        charts = json.loads(charts_path.read_text(encoding="utf-8")).get("charts", {}) if charts_path.exists() else {}
        history = []
        for archived in sorted(folder.glob("*-outbox.json"))[-100:]:
            data = json.loads(archived.read_text(encoding="utf-8"))
            history.extend(data.get("local_cases", []))
        unique = {}
        for case in history:
            unique.setdefault(case["case_id"], case)
        def model_call(prompt):
            receipt.write_text(json.dumps({"started_at": now.isoformat(), "provider": "ollama_local", "attempts": attempts+1, "input_coverage": coverage}), encoding="utf-8")
            raw = provider._request(local, prompt, timeout=(5,480),
                                    format_schema=response_schema(normalize_items(items, now), public_share_catalog()))
            (folder / (now.date().isoformat()+"-model-response.txt")).write_text(raw, encoding="utf-8")
            return raw
        try:
            result = local_scan(scan_brief, items, charts, list(unique.values()), now,
                                model_call, public_share_catalog(), prior=prior)
        except Exception as exc:
            # Record a bounded failure without exposing provider errors or keys.
            (folder / (now.date().isoformat()+"-failure.json")).write_text(json.dumps({
                "failure_type": type(exc).__name__, "at": now.isoformat()}), encoding="utf-8")
            payload = {"brief_id": brief["brief_id"], "received_at": now.isoformat(), "provider": "ollama_local",
                       "model": local.model, "matches": [], "articles": [],
                       "state": "LOCAL_OLLAMA_UNAVAILABLE_OR_INVALID_RESPONSE",
                       "previous_brief_id": state.get("previous_week", {}).get("brief_id")}
            requests.post(base+"/scan", json=payload, headers=headers, timeout=30, allow_redirects=False)
            return {"state": payload["state"], "trading_weight": 0}
        if result["state"] != "LOCAL_OLLAMA_SCAN_COMPLETE":
            return {"state": result["state"], "trading_weight": 0}
        fields = ("category", "description", "instrument_ids", "evidence_ids", "confidence")
        matches = [{**{k: c[k] for k in fields if k != "confidence"}, "confidence": c["model_confidence"]} for c in result["cases"]]
        payload = {"brief_id": brief["brief_id"], "received_at": now.isoformat(), "provider": "ollama_local",
                   "model": local.model, "articles": result["articles"], "matches": matches,
                   "research": {c["case_id"]: c["historical_research"] for c in result["cases"]},
                   "local_cases": result["cases"], "input_coverage": coverage, "previous_brief_id": state.get("previous_week", {}).get("brief_id")}
        outbox.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")
    response = requests.post(base+"/scan", json=payload, headers=headers, timeout=30, allow_redirects=False)
    return {"state": "LOCAL_RESEARCH_UPLOADED" if response.status_code == 202 else "UPLOAD_FAILED_LOCAL_COPY_RETAINED",
            "http_status": response.status_code, "cases": len(payload["matches"]), "trading_weight": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true", help="Use only the fixed local dashboard at 127.0.0.1:5000")
    parser.add_argument("--brief-file")
    parser.add_argument("--edition-date")
    parser.add_argument("--retry-failed", action="store_true", help="At most four bounded manual retries after repairing a failed local scan")
    args = parser.parse_args()
    from ai_config import project_environment
    try:
        result = run(project_environment(), brief_file=args.brief_file, edition_date=args.edition_date, retry_failed=args.retry_failed, local=args.local)
    except Exception:
        result = {"state": "WEEKLY_RESEARCH_UNAVAILABLE_LOCAL_DATA_RETAINED"}
    print(json.dumps(result))
    return 0 if result["state"] in {"WEEKLY_BRIEF_IMPORTED", "LOCAL_RESEARCH_UPLOADED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
