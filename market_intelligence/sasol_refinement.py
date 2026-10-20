"""One operational prospective paired shadow experiment; no historical/AI admission."""
from copy import deepcopy
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from importlib import import_module
from pathlib import Path

from . import research_calendar as calendar
from . import calendar_outcomes as sources
from application.opportunities.swing_technical import snapshot
from domain.policy.swing_shadow import build_policy, simulate, rules

ACCOUNT = "sasol-paired-refinement-v1"
VERSION = "sasol-paired-refinement-v1"
CONFIG = {"instrument": "SASOL", "benchmark": "ETF_STX40", "horizon_sessions": 3,
    "baseline_volume_gt": 1.0, "candidate_volume_gt": 1.2,
    "changed_components": ["relative_volume_minimum"], "minimum_informative_pairs": 20,
    "execution_rules": rules(), "overlap_policy": "ONE_PAIRED_EPISODE_AT_A_TIME",
    "costs_bps": [10, 25, 50], "automatic_promotion": False}


def _implementation():
    """Bind all numerical/source implementations, including this coordinator."""
    names = (__name__, "application.opportunities.swing_technical", "domain.features.technical",
             "domain.policy.swing_shadow", "market_intelligence.calendar_outcomes",
             "application.opportunities.swing_research", "application.opportunities.public_research",
             "application.opportunities.swing_data_quality", "market_intelligence.research_calendar")
    return {name: sha256(Path(import_module(name).__file__).read_text(encoding="utf-8").encode()).hexdigest()
            for name in names}


def _close_cents(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Actual benchmark close required")
    amount = Decimal(str(value)) * 100
    if not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value():
        raise ValueError("Exact benchmark close cents required")
    return int(amount)


def _dependencies(share, benchmark):
    return {"share": {b["timestamp"]: sources._units(b, "SASOL") for b in share["bars"]},
            "benchmark_close": {b["timestamp"]: _close_cents(b["close"]) for b in benchmark["bars"]}}


def _audit_dependencies(repo, share, benchmark, rid, now):
    current = _dependencies(share, benchmark)
    for episode in _rows(repo, "sasol-episode", now):
        for kind, original in episode["feature_dependencies"].items():
            for session, value in original.items():
                # A rolled-off date is unknown, not an asserted revision.
                if session in current[kind] and value != current[kind][session]:
                    _save(repo, "sasol-source-revision", [episode["record_id"], rid, kind, session],
                          {"session": session, "dataset_id": rid, "affected_episode_id": episode["record_id"],
                           "dependency": kind, "original_sha256": calendar._hash(value),
                           "revised_sha256": calendar._hash(current[kind][session])}, now)


def _rows(repo, kind, now):
    rows = repo.paper_records(ACCOUNT, kind, as_of=calendar._at(now).isoformat(), limit=2000)
    if len(rows) >= 2000:
        raise ValueError("Explicit refinement archive review required")
    return rows


def _save(repo, kind, identity, value, now):
    rid = kind + "-" + calendar._hash([VERSION, identity])
    old = repo.paper_record(rid)
    if old:
        return old
    repo.create_paper_account(ACCOUNT, {"mode": "PAPER", "purpose": "SHADOW_EXPERIMENT_NO_BALANCE"})
    row = {**value, "record_id": rid, "version": VERSION, "received_at": calendar._at(now).isoformat(),
           "live_execution": False, "automatic_promotion": False}
    repo.save_paper_record(rid, ACCOUNT, kind, row["received_at"], row)
    return row


def _input(stored, rid, dataset, now):
    share, benchmark = sources._whole_chart(dataset, "SASOL"), sources._whole_chart(dataset, "ETF_STX40")
    endpoints = [sources._endpoint(chart, key, stored, rid, chart["bars"][-1])
                 for chart, key in ((share, "SASOL"), (benchmark, "ETF_STX40"))]
    if endpoints[0]["session"] != endpoints[1]["session"]:
        raise ValueError("Aligned newest source endpoints required")
    if any(calendar._at(e["usable_at"]) > now or now-calendar._at(e["acquired_at"]) > timedelta(days=4)
           or now-sources._available_at(e["session"]) > timedelta(days=4) for e in endpoints):
        raise ValueError("Fresh completed actually acquired endpoints required")
    # Whole stock OHLCV is used for features; benchmark consumes its close-only path.
    for bar in share["bars"]:
        sources._units(bar, "SASOL")
    return share, benchmark, endpoints


def _bar(units):
    return {"timestamp": units["session"], **{key: units[key]/100 for key in ("open", "high", "low", "close")},
            "volume": units["volume"]}


def _replay(repo, episode, observations, now):
    for arm, policy in episode["policies"].items():
        if repo.paper_record("sasol-arm-result-" + calendar._hash([VERSION, [episode["record_id"], arm]])):
            continue
        later = sorted([o for o in observations if o["session"] > episode["signal_session"]
                        and calendar._at(o["received_at"]) > calendar._at(episode["received_at"])], key=lambda o: o["session"])
        # Entry uses the real receipt deadline, not the session-availability proxy.
        decision = calendar._at(episode["received_at"])
        expiry = decision + timedelta(days=CONFIG["execution_rules"]["entry_expiry_calendar_days"])
        eligible = [o for o in later if sources._available_at(o["session"]) > decision]
        actual_expired = now > expiry and (not eligible or calendar._at(eligible[0]["received_at"]) > expiry)
        if actual_expired:
            later = []
        chart = {"symbol": policy["source_symbol"], "interval": "1d", "currency": "ZAR",
                 "bars": [episode["signal_bar"]] + [o["bar"] for o in later]}
        result = simulate(policy, chart, evaluated_at=now.isoformat(), horizon_sessions=CONFIG["horizon_sessions"])
        if actual_expired and policy["state"] == "SHADOW_READY":
            result.update(state="EXPIRED", reason="ACTUAL_RECEIPT_ENTRY_WINDOW_EXPIRED")
        # Preserve actual acquisition/receipt times separately from session proxies.
        receipts = {o["session"]: o["received_at"] for o in later}
        for key in ("entry", "exit"):
            session = result.get(key + "_session")
            if session:
                result[key + "_price_available_at_proxy"] = result[key + "_observed_at"]
                result[key + "_observed_at"] = receipts[session]
        _save(repo, "sasol-arm-progress", [episode["record_id"], arm, calendar._hash(result)],
              {"episode_id": episode["record_id"], "arm": arm, "result": result}, now)
        if result["state"] in {"CLOSED", "NO_SETUP", "BLOCKED", "EXPIRED", "INVALIDATED"}:
            _save(repo, "sasol-arm-result", [episode["record_id"], arm],
                  {"episode_id": episode["record_id"], "arm": arm, "result": result}, now)


def _complete(episode, results):
    return all(any(r["episode_id"] == episode["record_id"] and r["arm"] == arm for r in results)
               for arm in ("baseline", "candidate"))


def _review(repo, now):
    episodes, results = _rows(repo, "sasol-episode", now), _rows(repo, "sasol-arm-result", now)
    revisions = _rows(repo, "sasol-source-revision", now)
    bad_sessions = {r["session"] for r in revisions if not r.get("affected_episode_id")}
    bad_episodes = {r["affected_episode_id"] for r in revisions if r.get("affected_episode_id")}
    pairs, excluded = [], 0
    for episode in sorted(episodes, key=lambda r: r["received_at"]):
        if not _complete(episode, results):
            continue
        arms = {r["arm"]: r["result"] for r in results if r["episode_id"] == episode["record_id"]}
        used = {episode["signal_session"]} | {b["timestamp"] for r in arms.values() for b in r.get("path", [])}
        if used & bad_sessions or episode["record_id"] in bad_episodes:
            excluded += 1
            continue
        if any(r["state"] == "CLOSED" for r in arms.values()):
            pairs.append(arms)
    metrics = {}
    for arm in ("baseline", "candidate"):
        net = {str(cost): [p[arm].get("net_return_scenarios", {}).get(str(cost), 0.0) for p in pairs]
               for cost in CONFIG["costs_bps"]}
        equity = peak = 1.0
        drawdown = 0.0
        for value in net["10"]:
            equity *= 1 + value
            peak = max(peak, equity)
            drawdown = max(drawdown, (peak-equity)/peak)
        metrics[arm] = {"closed_trades": sum(p[arm]["state"] == "CLOSED" for p in pairs),
            "mean_net_return": {k: sum(v)/len(v) if v else None for k, v in net.items()},
            "unit_notional_drawdown_10bps": drawdown if pairs else None}
    delta = {str(cost): (metrics["candidate"]["mean_net_return"][str(cost)] - metrics["baseline"]["mean_net_return"][str(cost)])
             if pairs else None for cost in CONFIG["costs_bps"]}
    if len(pairs) < CONFIG["minimum_informative_pairs"]:
        decision = "INSUFFICIENT_EVIDENCE_KEEP_BASELINE"
    elif all(v > 0 for v in delta.values()) and metrics["candidate"]["unit_notional_drawdown_10bps"] <= metrics["baseline"]["unit_notional_drawdown_10bps"]:
        decision = "CANDIDATE_FOR_INDEPENDENT_REVIEW_NOT_PROMOTION"
    elif all(v <= 0 for v in delta.values()):
        decision = "REJECT_CANDIDATE_KEEP_BASELINE"
    else:
        decision = "KEEP_BASELINE_MIXED_COST_OR_DRAWDOWN_EVIDENCE"
    value = {"decision": decision, "informative_pairs": len(pairs), "revision_excluded_pairs": excluded,
        "episodes_recorded": len(episodes), "terminal_pairs": sum(_complete(e, results) for e in episodes),
        "metrics": metrics, "candidate_minus_baseline": delta,
        "next_test_request": None if len(pairs) < CONFIG["minimum_informative_pairs"] else
            {"state": "PROPOSED_NEW_FUTURE_EXPERIMENT_ONLY", "parameter": "rsi_max", "baseline": 70,
             "candidate": 65, "all_other_parameters_fixed": True, "automatic_start": False},
        "cost_basis": "HYPOTHETICAL_10_25_50_BPS_NOT_VERIFIED_OST",
        "metric_scope": "SEQUENTIAL_EXPLORATORY_SAMPLED_PATH_UNIT_NOTIONAL_NOT_ACCOUNT_PORTFOLIO_OR_PROVEN_EDGE",
        "coverage": "Only actually captured endpoints; missing exchange sessions can hide stop/target touches. Twenty informative pairs trigger review, not statistical proof.",
        "candidate_has_no_trades": metrics["candidate"]["closed_trades"] == 0}
    return _save(repo, "sasol-review", calendar._hash(value), value, now)


@calendar._write
def tick(repo, now):
    now = calendar._at(now)
    definition_id = "sasol-definition-" + calendar._hash([VERSION, "fixed-pair"])
    definition = repo.paper_record(definition_id)
    implementations = _implementation()
    if definition and (definition["config"] != CONFIG or definition["implementation_sha256"] != implementations):
        raise ValueError("Frozen experiment requires a new explicit version")
    datasets = sources._datasets(repo, now)
    if not definition:
        definition = _save(repo, "sasol-definition", "fixed-pair", {"config": deepcopy(CONFIG), "implementation_sha256": implementations,
            "initial_dataset_id": datasets[-1][1] if datasets else None,
            "historical_admission": False, "source_semantics": "UNVERIFIED_ACCEPTED_FOR_NUMERICAL_SHADOW_ONLY"}, now)
        datasets = datasets[-1:]
    processed = {m["dataset_id"] for m in _rows(repo, "sasol-import", now)}
    for stored, rid, data in datasets:
        if rid in processed or (stored < calendar._at(definition["received_at"]) and rid != definition["initial_dataset_id"]):
            continue
        try:
            share, benchmark, proof = _input(stored, rid, data, now)
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            _save(repo, "sasol-input-audit", rid, {"dataset_id": rid, "state": "INPUT_UNAVAILABLE", "reason_type": type(exc).__name__}, now)
            continue
        _audit_dependencies(repo, share, benchmark, rid, now)
        observations = _rows(repo, "sasol-observation", now)
        for old in observations:
            for key, chart in (("share_units", share), ("benchmark_units", benchmark)):
                matching = next((b for b in chart["bars"] if b["timestamp"] == old["session"]), None)
                if matching is not None and sources._units(matching, "SASOL" if key == "share_units" else "ETF_STX40") != old[key]:
                    _save(repo, "sasol-source-revision", [old["record_id"], rid, key],
                          {"session": old["session"], "dataset_id": rid, "original_observation_id": old["record_id"]}, now)
        day = proof[0]["session"]
        if not observations or day > max(o["session"] for o in observations):
            units = sources._units(share["bars"][-1], "SASOL")
            obs = _save(repo, "sasol-observation", day, {"session": day, "bar": _bar(units),
                "share_units": units, "benchmark_units": sources._units(benchmark["bars"][-1], "ETF_STX40"),
                "source_proofs": proof, "dataset_id": rid, "initial_context": not bool(observations)}, now)
            observations.append(obs)
            episodes = _rows(repo, "sasol-episode", now)
            for episode in episodes:
                _replay(repo, episode, observations, now)
            active = any(not _complete(e, _rows(repo, "sasol-arm-result", now)) for e in episodes)
            features = snapshot(share, evaluated_at=now, benchmark_chart=benchmark)
            if active:
                state = "BUSY_PAIRED_EPISODE_CONTROL"
            elif features["state"] != "AVAILABLE":
                state = "FEATURES_UNAVAILABLE_CONTROL"
            else:
                baseline = build_policy(features, decision_at=now.isoformat())
                candidate = deepcopy(baseline)
                if baseline["state"] == "SHADOW_READY" and features["values"]["relative_volume20"] <= CONFIG["candidate_volume_gt"]:
                    candidate.update(state="NO_SETUP", reasons=["CANDIDATE_VOLUME_GT1_2_NOT_MET"])
                episode = _save(repo, "sasol-episode", day, {"signal_session": day, "signal_bar": obs["bar"],
                    "source_observation_id": obs["record_id"], "features": features,
                    "feature_dependencies": _dependencies(share, benchmark),
                    "implementation_sha256": implementations,
                    "policies": {"baseline": baseline, "candidate": candidate}, "config_sha256": calendar._hash(CONFIG)}, now)
                _replay(repo, episode, observations, now)
                state = "PAIRED_SIGNAL_RECORDED"
            _save(repo, "sasol-day", day, {"session": day, "state": state, "dataset_id": rid,
                "feature_state": features["state"], "source_observation_id": obs["record_id"]}, now)
        _save(repo, "sasol-import", rid, {"dataset_id": rid, "dataset_received_at": stored.isoformat()}, now)
    # Expiry/review also progresses without a new import; reads do neither.
    for episode in _rows(repo, "sasol-episode", now):
        _replay(repo, episode, _rows(repo, "sasol-observation", now), now)
    review = _review(repo, now)
    return {"state": "SASOL_SHADOW_LOOP_OPERATIONAL", "review_id": review["record_id"], "model_calls": 0, "live_execution": False}


def status(repo, now):
    definitions = _rows(repo, "sasol-definition", now)
    days, results = _rows(repo, "sasol-day", now), _rows(repo, "sasol-arm-result", now)
    reviews = _rows(repo, "sasol-review", now)
    progress = _rows(repo, "sasol-arm-progress", now)
    latest = {}
    for row in sorted(progress, key=lambda r: r["received_at"]):
        latest[(row["episode_id"], row["arm"])] = row
    intact = not definitions or (definitions[0]["config"] == CONFIG and definitions[0]["implementation_sha256"] == _implementation())
    return {"state": "BLOCKED_DEFINITION_DRIFT" if not intact else ("OPERATIONAL_SHADOW_ONLY" if definitions else "NOT_STARTED"),
        "definition_integrity": intact, "config": deepcopy(CONFIG),
        "registered_at": definitions[0]["received_at"] if definitions else None,
        "observed_sessions": len(_rows(repo, "sasol-observation", now)),
        "latest_session": max((d["session"] for d in days), default=None),
        "day_controls": dict(Counter(d["state"] for d in days)),
        "arm_states": {arm: dict(Counter(r["result"]["state"] for r in results if r["arm"] == arm)) for arm in ("baseline", "candidate")},
        "current_arm_states": {arm: dict(Counter(r["result"]["state"] for r in latest.values() if r["arm"] == arm)) for arm in ("baseline", "candidate")},
        "episodes": len(_rows(repo, "sasol-episode", now)), "latest_review": reviews[0] if reviews else None,
        "revision_audits": len(_rows(repo, "sasol-source-revision", now)),
        "input_audits": len(_rows(repo, "sasol-input-audit", now)),
        "live_execution": False, "automatic_promotion": False, "historical_admission": False,
        "limitations": "Sequential exploratory sampled-path shadow; missing exchange sessions may hide stop/target touches. Twenty informative pairs trigger independent review, not statistical proof. Actual newest capture endpoints only; missing sessions stay missing. Unit-notional close proxies and assumed costs; no broker fills, news-label dependency or validated edge."}
