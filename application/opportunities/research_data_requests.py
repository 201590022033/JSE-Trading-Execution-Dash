"""Local research data chores and immutable canonical-membership requests.

No ranking, providers, passwords, orders or source admission. Missing/stale
rankings never retire candidates. Background requests wait for operator login.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
import re
from zoneinfo import ZoneInfo

from shadow_learning import timestamp
from .public_research import public_share_catalog, _identities, _available_at
from .swing_research import latest_dataset
from .ost_data import catalog
from .swing_data_quality import real_ohlc

ACCOUNT = "research-data-requests-v1"
VERSION = "research-data-requests-v1"
SAST = ZoneInfo("Africa/Johannesburg")
LIMIT = 2000


def _now(value):
    return timestamp(value.isoformat() if isinstance(value, datetime) else value)


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _rows(repo, kind, now):
    rows = repo.paper_records(ACCOUNT, kind, as_of=now.isoformat(), limit=LIMIT)
    if len(rows) >= LIMIT:
        raise ValueError("Explicit request archive review required")
    return rows


def _save(repo, kind, identity, body, now):
    rid = kind+"-"+_hash(identity)
    prior = repo.paper_record(rid)
    if prior:
        return prior
    repo.create_paper_account(ACCOUNT, {"mode": "PAPER", "purpose": "RESEARCH_ONLY_NO_BALANCE"})
    record = {**body, "record_id": rid, "version": VERSION, "received_at": now.isoformat(), "trading_weight": 0}
    repo.save_paper_record(rid, ACCOUNT, kind, now.isoformat(), record)
    return record


def _configuration(account_id=None):
    from .paper_host import configured_paper
    config = configured_paper()
    return account_id or (config.account_id if config else None), config.max_price_age_seconds if config and account_id in (None, config.account_id) else 345600


def membership(repo, now, *, account_id=None):
    """Read the exact published worker ranking; never run a ranker or fallback."""
    now = _now(now)
    account_id, max_age = _configuration(account_id)
    state = repo.paper_account(account_id) if account_id else None
    rid = state.get("ranking_record_id") if state else None
    snapshot = repo.paper_record(rid) if rid else None
    if not snapshot:
        return {"state": "NO_FROZEN_TOP5", "members": [], "ranking_record_id": None}
    if not isinstance(snapshot.get("opportunities"), list) or snapshot.get("mode") != "PAPER":
        return {"state": "INCOMPLETE_FROZEN_TOP5", "members": [], "ranking_record_id": rid}
    evaluated = timestamp(snapshot["evaluated_at"])
    if evaluated > now or (now-evaluated).total_seconds() > max_age:
        return {"state": "STALE_FROZEN_TOP5", "members": [], "ranking_record_id": rid,
                "evaluated_at": evaluated.isoformat(), "ranking_sha256": _hash(snapshot)}
    shares = public_share_catalog()
    identities = {_identities(key, value)[0].instrument_id: key for key, value in shares.items()}
    identities.update({key: key for key in shares})
    rows = [row for row in snapshot.get("opportunities", []) if type(row.get("rank")) is int and 1 <= row["rank"] <= 5]
    mapped = [identities.get(row.get("instrument_id")) for row in sorted(rows, key=lambda r: r["rank"])]
    if any(key is None for key in mapped) or len(set(mapped)) != len(mapped) or len({r["rank"] for r in rows}) != len(rows):
        raise ValueError("Exact registered unique Top 5 identities required")
    return {"state": "INCOMPLETE_FROZEN_TOP5" if snapshot.get("unavailable") else "CURRENT_FROZEN_TOP5", "members": mapped, "ranking_record_id": rid,
            "strategy_profile_id": snapshot.get("strategy_profile_id"), "strategy_profile_version": snapshot.get("strategy_profile_version"),
            "evaluated_at": evaluated.isoformat(), "ranking_sha256": _hash(snapshot)}


def _coverage(dataset, key, now, max_age=345600):
    charts = (dataset or {}).get("charts", {})
    research = (dataset or {}).get("research_charts", {})
    benchmark = charts.get("ETF_STX40")
    def receipt(chart, provider, instrument):
        if not chart or not chart.get("bars"):
            return {"state": "MISSING", "daily_current": False, "bars": 0}
        p, bars = chart.get("provenance", {}), chart["bars"]
        try:
            acquired = timestamp(p["acquired_at"])
            session = datetime.fromisoformat(bars[-1]["timestamp"][:10]).replace(tzinfo=timezone.utc)
            available = _available_at(bars[-1]["timestamp"])
            completed = available <= now and session + timedelta(hours=15) <= acquired
            route = catalog()[instrument]
            identity = (chart.get("symbol") == route["symbol"] and chart.get("currency") == "ZAR" and chart.get("interval") == "1d"
                        and p.get("origin_symbol") == route["ost_code"] + (".JSE" if provider == "IRESS" else ""))
            real = all(real_ohlc(bar) and not bar.get("is_estimated") and not bar.get("synthetic")
                       and type(bar.get("volume")) in (int, float) and math.isfinite(bar["volume"]) and bar["volume"] >= 0 and bar["volume"] == int(bar["volume"])
                       for bar in bars) if provider == "IRESS" else True
            correct = identity and real and p.get("provider") == provider and isinstance(p.get("source_sha256"), str) and bool(re.fullmatch("[0-9a-f]{64}", p["source_sha256"]))
            from .session_freshness import current_chart
            session_current = current_chart(chart, now)
            current = (correct and completed and (session_current if session_current is not None else
                (acquired <= now and (now-available).total_seconds() <= max_age)))
        except (KeyError, TypeError, ValueError):
            current = False
        return {"state": "CURRENT_CAPTURE" if current else "REFRESH_REQUIRED", "daily_current": bool(current),
                "bars": len(bars), "latest_session": bars[-1]["timestamp"], "acquired_at": p.get("acquired_at"),
                "source_sha256": p.get("source_sha256"), "latest_ohlc_valid": real_ohlc(bars[-1])}
    ost = receipt(charts.get(key), "OST", key)
    iress = receipt(research.get(key), "IRESS", key)
    bench = receipt(benchmark, "OST", "ETF_STX40")
    aligned = bool(iress.get("latest_session") and iress.get("latest_session") == bench.get("latest_session") == ost.get("latest_session"))
    current = ost["daily_current"] and iress["daily_current"] and iress.get("latest_ohlc_valid") and bench["daily_current"] and aligned
    return {"instrument_id": key, "ost": ost, "iress": iress, "benchmark": bench,
            "daily_ready": bool(current), "benchmark_aligned": aligned,
            "history_target_sessions": 600, "history_target_met": min(ost["bars"], iress["bars"], bench["bars"]) >= 600,
            "historical_ai_admitted": False, "definitions": "ADJUSTMENT_ACTIONS_VOLUME_AVAILABILITY_UNVERIFIED"}


def sync_requests(repo, now, *, account_id=None):
    """Light clock operation: persist new membership and login-dependent requests."""
    now = _now(now)
    observed = membership(repo, now, account_id=account_id)
    with repo.transaction():
        if repo.backend == "postgresql":
            lock = int.from_bytes(sha256(ACCOUNT.encode()).digest()[:8], "big", signed=True)
            repo._job_sql("SELECT pg_advisory_xact_lock(?)", (lock,), rows=True)
        previous = _rows(repo, "data-membership", now)
        last = max(previous, key=lambda r: r["received_at"], default=None)
        if observed["state"] == "CURRENT_FROZEN_TOP5":
            entered = sorted(set(observed["members"])-set(last["members"] if last else []))
            left = sorted(set(last["members"] if last else [])-set(observed["members"]))
            _save(repo, "data-membership", observed["ranking_record_id"], {**observed, "entered": entered, "left": left,
                  "prior_data_retained": True}, now)
        tracked = set(observed["members"]) | {"SASOL"}
        for row in previous:
            tracked.update(row["members"])
        shares = public_share_catalog()
        for key in sorted(tracked):
            if key not in shares:
                continue
            for requirement in ("OST_HLCV_HISTORY", "IRESS_WHOLE_OHLCV", "SENS_AND_CORPORATE_ACTIONS", "SOURCE_DEFINITION_EVIDENCE"):
                _save(repo, "data-request", [key, requirement], {"instrument_id": key, "requirement": requirement,
                    "state": "WAITING_FOR_OPERATOR_LOGIN_OR_EVIDENCE", "purpose": "FORWARD_RESEARCH_ONLY",
                    "history_target_sessions": 600, "created_from_ranking_id": observed.get("ranking_record_id"),
                    "automatic_download": False, "password_stored": False}, now)
        for requirement in ("BENCHMARK_AND_SECTOR_HISTORY", "GOLD_USDZAR_REFERENCE_CONTRACTS", "EXECUTION_COST_AND_FILL_EVIDENCE", "GENERALIZE_NUMERICAL_IRESS_ROUTING_BEYOND_SASOL"):
            _save(repo, "data-request", ["MARKET_CONTEXT", requirement], {"instrument_id": "MARKET_CONTEXT", "requirement": requirement,
                "state": "WAITING_FOR_OPERATOR_LOGIN_OR_EVIDENCE", "purpose": "SEPARATE_CONTEXT_OR_EXECUTION_EVIDENCE",
                "automatic_download": False, "password_stored": False}, now)
        _save(repo, "data-routine", "daily-ost-iress", {"title": "Daily OST / IRESS data import", "time_zone": "Africa/Johannesburg",
            "weekdays": [0, 1, 2, 3, 4], "hour": 8, "kind": "OPERATOR_MAINTENANCE_NOT_MARKET_EVENT"}, now)
    return status(repo, now, account_id=account_id)


def storage_estimate(dataset, *, slots=5, weekly_churn=5, retained_weeks=12):
    if any(type(v) is not int or v < 1 for v in (slots, weekly_churn, retained_weeks)) or slots > len(public_share_catalog()) or weekly_churn > len(public_share_catalog()) or retained_weeks > 520:
        raise ValueError("Bounded positive planning assumptions required")
    bars = [b for c in [*(dataset or {}).get("charts", {}).values(), *(dataset or {}).get("research_charts", {}).values()] for b in c.get("bars", [])]
    per_bar = max(200, round(sum(len(json.dumps(b, separators=(",", ":")).encode()) for b in bars)/len(bars))) if bars else 300
    unique = min(len(public_share_catalog()), slots+weekly_churn*retained_weeks)
    series = slots*2+6  # Two independent stock sources, Top40/3sectors/2macro planning references.
    snapshot = series*600*per_bar
    return {"state": "PLANNING_ESTIMATE_NOT_RETENTION_ENFORCEMENT", "active_slots": slots,
        "measured_current_dataset_bytes": len(json.dumps(dataset or {}, sort_keys=True, separators=(",", ":")).encode()),
        "measured_bar_count": len(bars), "measured_series_count": len((dataset or {}).get("charts", {}))+len((dataset or {}).get("research_charts", {})),
        "assumed_weekly_new_candidates": weekly_churn, "planning_weeks": retained_weeks,
        "maximum_unique_registered_candidates": unique, "measured_or_assumed_bytes_per_bar": per_bar,
        "six_context_series_include_unverified_macro_contracts": True,
        "active_history_bytes": snapshot, "incremental_price_bytes_per_252_sessions": series*252*per_bar,
        "full_daily_snapshot_bytes_per_252_sessions": snapshot*252,
        "additional_candidate_history_bytes": max(0, unique-slots)*2*600*per_bar,
        "proposed_30_daily_12_monthly_snapshot_copy_bytes": snapshot*42,
        "news_reports_raw_documents_and_database_backup_costs_not_included": True,
        "retention_applied": False, "automatic_deletion": False,
        "assumptions": "600 completed bars/series; 252 planning sessions, not a verified exchange calendar. Hash reuse avoids reloading returning candidates. Full PDF/news/model/backup growth is additional."}


def status(repo, now, *, account_id=None):
    now = _now(now)
    observed = membership(repo, now, account_id=account_id)
    histories = _rows(repo, "data-membership", now)
    latest = max(histories, key=lambda r: r["received_at"], default=None)
    current = set(observed["members"]) if observed["state"] == "CURRENT_FROZEN_TOP5" else set(latest["members"] if latest else [])
    tracked = current | {"SASOL"}
    for row in histories:
        tracked.update(row["members"])
    dataset = latest_dataset(repo)
    coverage = [_coverage(dataset, key, now, _configuration(account_id)[1]) for key in sorted(tracked)]
    for row in coverage:
        row['source_transform'] = (dataset or {}).get('source_transform_receipts', {}).get(row['instrument_id'])
    today = now.astimezone(SAST)
    ready = bool(coverage) and all(c["daily_ready"] for c in coverage if c["instrument_id"] in current | {"SASOL"})
    due = today.weekday() < 5 and today.hour >= 8 and not ready
    next_day = today.replace(hour=8, minute=0, second=0, microsecond=0)
    if next_day <= today:
        next_day += timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    routes = catalog()
    required = sorted(current | {"SASOL"})
    names = ", ".join(f"{key} ({routes[key]['ost_code']})" for key in required if key in routes)
    prompt = (f"Daily local swing-data import for {today.date().isoformat()} SAST. I have signed into Standard Bank OST and ViewPoint/IRESS in the Codex browser. "
        f"Use computer skills read-only to capture {names}, plus ETF_STX40 and required sector context. Read the saved research-data requests first. "
        "For each share retain the native OST HLCV export and a SEPARATE complete daily IRESS OHLCV table; target600 completed sessions where available. "
        "OST omits Open: never copy IRESS Open into an OST bar and never substitute prior close, auction or first intraday price. Exclude the live row. "
        "Keep actual acquisition time, raw bytes/hash and exact symbol/units; preserve older captures, compare revisions in integer cents/whole volume, "
        "then use the existing local importers/collector and accepted local PostgreSQL ingress. No Railway upload. Retest numerical source/benchmark alignment and 3/4/5 observed-session progress. "
        "Queue missing history, SENS/actions and source-definition evidence separately; do not backdate availability or relax B5/AI/execution gates. "
        "Reconcile the current frozen canonical Top5 and enqueue any newly entered share; retain former candidates and their historical decisions. "
        "No orders, no password storage, no chargeable live quote requests. Report actual imports, remaining gaps and disk growth.")
    covered = {row["instrument_id"]: row for row in coverage}
    requests = []
    for row in _rows(repo, "data-request", now):
        cov = covered.get(row["instrument_id"])
        state = "EVIDENCE_REVIEW_REQUIRED"
        if row["requirement"] in {"OST_HLCV_HISTORY", "IRESS_WHOLE_OHLCV"} and cov:
            source = cov["ost"] if row["requirement"] == "OST_HLCV_HISTORY" else cov["iress"]
            state = ("CURRENT_HISTORY_PRESENT" if source["daily_current"] and source["bars"] >= 600 else
                     "CURRENT_CAPTURE_HISTORY_SHORT" if source["daily_current"] else
                     "DAILY_REFRESH_REQUIRED" if source["bars"] else "WAITING_FOR_LOGIN_AND_INITIAL_HISTORY")
        priority = ("CURRENT_TOP5" if row["instrument_id"] in current else "SASOL_PILOT" if row["instrument_id"] == "SASOL" else
                    "SHARED_CONTEXT" if row["instrument_id"] == "MARKET_CONTEXT" else "RETAINED_PRIOR_CANDIDATE")
        requests.append({**row, "readiness": state, "priority": priority})
    return {"state": "RESEARCH_DATA_OPERATIONS_ONLY", "membership": observed, "current_members": sorted(current),
        "configured_scope_note": "Only published canonical candidates are Top5 members; Sasol remains an explicit pilot. Missing/stale ranking never clears prior requests.",
        "coverage": coverage, "coverage_scope": "LATEST_REGISTERED_DATASET_NOT_ALL_LOCAL_FILES", "requests": requests, "tracked_candidates": len(tracked),
        "daily_reminder": {"state": "IMPORT_REQUIRED" if due else "CURRENT" if ready else "NEXT_WEEKDAY_WINDOW",
            "due": due, "time_zone": "Africa/Johannesburg", "weekday_time": "08:00", "next_window": next_day.isoformat(),
            "all_required_current_today": ready, "exchange_holidays": "NOT_ASSUMED_OPERATOR_CHECK"},
        "copyable_prompt": prompt, "login_urls": ["https://securities.standardbank.co.za/ost/", "https://viewpoint.iress.co.za/st/"],
        "storage": storage_estimate(dataset), "trading_weight": 0, "live_execution": False, "automatic_download": False}
