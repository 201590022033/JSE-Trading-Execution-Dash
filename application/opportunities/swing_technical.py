"""Compact daily Swing shadow evidence; never changes benchmark order admission."""
from hashlib import sha256
import json
from math import isfinite
from datetime import timedelta

from domain.features.technical import _ema, candidate_rsi_wilder
from domain.strategy.attribution import fields, freeze_profile, reference, validate_frozen_profile
from shadow_learning import stable_id, timestamp

VERSION = "swing-ohlcv-wilder-v1"
DECISION_KIND = "swing-feature-decision"
OUTCOME_KIND = "swing-feature-outcome"
HORIZONS = (3, 4, 5)
READ_LIMIT = 5000
STRATEGY_FIELDS = {"strategy_profile_id": "jse_swing_3_5d", "strategy_profile_version": "1.1.0"}


def usable_bars(chart, now):
    from .public_research import _available_at
    if not chart or chart.get("interval") != "1d" or chart.get("currency") != "ZAR":
        raise ValueError("daily ZAR chart required")
    bars = [row for row in chart.get("bars", ()) if _available_at(row["timestamp"]) <= now]
    times = [_available_at(row["timestamp"]) for row in bars]
    if not bars or any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError("ordered completed sessions required")
    if any(not isfinite(float(row["close"])) or float(row["close"]) <= 0 for row in bars):
        raise ValueError("positive finite closes required")
    from .session_freshness import daily_clock_allowed
    current = daily_clock_allowed(times[-1], now, 4*86400) if chart.get('provenance') else now-times[-1] <= timedelta(days=4)
    if not current:
        raise ValueError("stale daily chart")
    return bars


def snapshot(chart, *, evaluated_at, benchmark_chart=None):
    """All calculations use only observable bars. Null means unavailable, not neutral."""
    from .public_research import _available_at
    now = timestamp(evaluated_at.isoformat() if hasattr(evaluated_at, "isoformat") else evaluated_at)
    try:
        bars = usable_bars(chart, now)
    except (ValueError, KeyError, TypeError, OverflowError):
        unavailable = {"version": VERSION, "state": "UNAVAILABLE", "reason": "INVALID_OR_STALE_DAILY_CHART"}
        if chart and chart.get("interval") == "1d" and chart.get("currency") == "ZAR":
            try:
                from .swing_data_quality import diagnostics
                completed = [r for r in chart.get("bars", ()) if _available_at(r["timestamp"]) <= now]
                times = [_available_at(r["timestamp"]) for r in completed]
                if completed and all(a < b for a, b in zip(times, times[1:])):
                    quality = diagnostics(completed)
                    if quality["invalid_ohlc_count"]:
                        unavailable["data_quality"] = quality
            except (ValueError, KeyError, TypeError, OverflowError):
                pass
        return unavailable
    closes = [float(row["close"]) for row in bars]
    from .swing_data_quality import diagnostics, real_ohlc
    quality = diagnostics(bars)
    values = {"ema20": None, "ema50": None, "rsi14_wilder": None, "atr14_wilder": None,
              "relative_volume20": None, "prior_high10": None, "prior_low10": None,
              "prior_high20": None, "prior_low20": None, "relative_return20": None}
    missing = []
    if len(bars) >= 50:
        values.update(ema20=_ema(closes, 20), ema50=_ema(closes, 50))
    else:
        missing.append("EMA_REQUIRES_50_SESSIONS")
    rsi = candidate_rsi_wilder(closes)
    values["rsi14_wilder"] = rsi.value if rsi.available else None
    if not rsi.available:
        missing.append("RSI_REQUIRES_15_SESSIONS")
    try:
        ohlc = [(float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])) for row in bars]
        if any(not real_ohlc(row) for row in bars) or any(not all(isfinite(x) and x > 0 for x in row) or
               row[2] > min(row[0], row[3]) or row[1] < max(row[0], row[3]) for row in ohlc):
            raise ValueError("invalid OHLC")
        ranges = [max(row[1]-row[2], abs(row[1]-closes[i-1]), abs(row[2]-closes[i-1]))
                  for i, row in enumerate(ohlc) if i > 0]
        if len(ranges) >= 14:
            atr = sum(ranges[:14])/14
            for value in ranges[14:]:
                atr = (13*atr+value)/14
            values["atr14_wilder"] = atr
        else:
            missing.append("ATR_REQUIRES_15_OHLC_SESSIONS")
        for window in (10, 20):
            if len(bars) > window:
                prior = ohlc[-window-1:-1]
                values[f"prior_high{window}"] = max(row[1] for row in prior)
                values[f"prior_low{window}"] = min(row[2] for row in prior)
    except (KeyError, TypeError, ValueError, OverflowError):
        missing.append("REAL_OHLC_UNAVAILABLE")
    try:
        volumes = [float(row["volume"]) for row in bars[-21:]]
        if len(volumes) != 21 or any(not isfinite(x) or x < 0 for x in volumes) or sum(volumes[:-1]) <= 0:
            raise ValueError("volume unavailable")
        values["relative_volume20"] = volumes[-1]/(sum(volumes[:-1])/20)
    except (KeyError, TypeError, ValueError, OverflowError):
        missing.append("VOLUME_UNAVAILABLE")
    benchmark_source = None
    try:
        benchmark = usable_bars(benchmark_chart, now)
        by_date = {row["timestamp"][:10]: float(row["close"]) for row in benchmark}
        start, end = bars[-21]["timestamp"][:10], bars[-1]["timestamp"][:10]
        if benchmark[-1]["timestamp"][:10] != end:
            raise ValueError("benchmark latest session mismatch")
        values["relative_return20"] = closes[-1]/closes[-21]-by_date[end]/by_date[start]
        benchmark_source = {"symbol": benchmark_chart.get("symbol"), "start_session": start,
                            "end_session": end, "start_close": by_date[start], "end_close": by_date[end]}
    except (ValueError, KeyError, TypeError, IndexError, OverflowError):
        missing.append("ALIGNED_BENCHMARK_UNAVAILABLE")
    trend = None if values["ema50"] is None else closes[-1] > values["ema20"] > values["ema50"]
    breakout = None if values["prior_high20"] is None else closes[-1] > values["prior_high20"]
    pullback = None if values["ema20"] is None or values["prior_high10"] is None else (
        trend and closes[-2] <= _ema(closes[:-1], 20) and closes[-1] > values["ema20"])
    # Declared research geometry, not an admitted policy or executable quote.
    geometry = {"state": "UNAVAILABLE", "basis": "SIGNAL_CLOSE_REFERENCE_NOT_ENTRY_FILL"}
    if values["atr14_wilder"] is not None and values["prior_low10"] is not None:
        stop = min(values["prior_low10"], closes[-1]-values["atr14_wilder"])
        risk = closes[-1]-stop
        if 0 < stop < closes[-1] and risk > 0:
            geometry.update(state="SHADOW_REFERENCE", stop=stop,
                target_2r=closes[-1]+2*risk, risk_per_share=risk,
                stop_rule="LOWER_OF_PRIOR_10_SESSION_LOW_AND_ONE_ATR_BELOW_CLOSE")
    conditions = {"ema_uptrend": trend, "breakout20": breakout, "ema20_reclaim": pullback,
        "rsi_50_70": None if values["rsi14_wilder"] is None else 50 <= values["rsi14_wilder"] <= 70,
        "volume_above_prior20": None if values["relative_volume20"] is None else values["relative_volume20"] > 1,
        "outperforming_benchmark20": None if values["relative_return20"] is None else values["relative_return20"] > 0}
    core = None if missing or geometry["state"] != "SHADOW_REFERENCE" else (
        trend and (breakout or pullback) and conditions["rsi_50_70"] and
        conditions["volume_above_prior20"] and conditions["outperforming_benchmark20"])
    conditions["core_setup"] = core
    return {"version": VERSION, **STRATEGY_FIELDS, "state": "AVAILABLE" if not missing else "PARTIAL",
            "evaluated_at": now.isoformat(), "session": bars[-1]["timestamp"][:10],
            "available_at": _available_at(bars[-1]["timestamp"]).isoformat(),
            "last_close": closes[-1], "source_symbol": chart.get("symbol"),
            "source_bars": len(bars), "initialization": "FIRST_OBSERVED_CLOSE_EMA_INITIAL_SMA_WILDER",
            "source_sha256": sha256(json.dumps(bars, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
            "values": values, "missing": missing,
            **({"data_quality": quality} if quality["invalid_ohlc_count"] else {}),
            "benchmark_source": benchmark_source,
            "geometry": geometry,
            "conditions": conditions,
            "setup_state": "UNAVAILABLE" if core is None else "SHADOW_SETUP_PRESENT" if core else "NO_SHADOW_SETUP",
            "rule_basis": "PREREGISTERED_CANDIDATE_THRESHOLDS_NOT_OPTIMIZED_OR_VALIDATED",
            "governance": "SHADOW_ONLY_NOT_A_TRADE_SIGNAL"}


def record_and_label(repository, account_id, snapshots, charts, *, evaluated_at, strategy_definition=None):
    """One decision + three small labels. No top-five/positive-outcome selection."""
    from .public_research import _available_at, _identities, public_share_catalog, public_etf_catalog
    from domain.strategy import DEFAULT_STRATEGY_REGISTRY
    profile = DEFAULT_STRATEGY_REGISTRY.resolve("jse_swing_3_5d", "1.1.0")
    definition = strategy_definition or freeze_profile(profile)
    ref = validate_frozen_profile(definition)
    if ref != profile.reference:
        raise ValueError("unsupported Swing technical definition; retain exact retry version")
    repository.save_strategy_definition(definition)
    now = timestamp(evaluated_at.isoformat() if hasattr(evaluated_at, "isoformat") else evaluated_at)
    for key, evidence in snapshots.items():
        if evidence.get("version") != VERSION or "session" not in evidence:
            continue
        if timestamp(evidence["evaluated_at"]) > now or timestamp(evidence["available_at"]) > now:
            raise ValueError("Swing feature snapshot clock mismatch")
        if reference(evidence) != ref:
            raise ValueError("Swing feature snapshot strategy mismatch")
        catalog = {**public_share_catalog(), **public_etf_catalog()}
        if key not in catalog or evidence["source_symbol"] != catalog[key]["yahoo_symbol"]:
            raise ValueError("Swing feature source identity mismatch")
        decision_id = stable_id(DECISION_KIND, account_id, key, evidence["session"], VERSION, ref.strategy_profile_version)
        if repository.paper_record(decision_id) is None:
            repository.save_paper_record(decision_id, account_id, DECISION_KIND, now.isoformat(),
                {"decision_id": decision_id, "instrument_id": _identities(key, catalog[key])[0].instrument_id,
                 "instrument_key": key, "decision_at": now.isoformat(),
                 "features": evidence, **fields(ref)})
    decisions = repository.paper_records(account_id, DECISION_KIND, as_of=now.isoformat(), limit=READ_LIMIT)
    for decision in decisions:
        if reference(decision) != ref or decision["instrument_key"] not in charts:
            continue
        current_source = charts[decision['instrument_key']].get('provenance')
        frozen_source = decision['features'].get('source_provenance')
        if current_source or frozen_source:
            # A provider switch cannot silently label a previously frozen decision.
            if not current_source or not frozen_source or any(current_source[k] != frozen_source[k]
                    for k in ('provider', 'origin_symbol', 'price_basis', 'volume_basis')):
                continue
        try:
            bars = usable_bars(charts[decision["instrument_key"]], now)
            later = [bar for bar in bars if _available_at(bar["timestamp"]) > timestamp(decision["decision_at"])]
            # Truncated histories must not substitute a later entry after restart.
            if _available_at(bars[0]["timestamp"]) > timestamp(decision["decision_at"]):
                continue
        except (ValueError, KeyError, TypeError, OverflowError):
            continue
        for horizon in HORIZONS:
            if len(later) <= horizon:
                continue
            oid = stable_id(OUTCOME_KIND, decision["decision_id"], horizon)
            if repository.paper_record(oid) is not None:
                continue
            entry, exit_bar = later[0], later[horizon]
            gross = float(exit_bar["close"])/float(entry["close"])-1
            repository.save_paper_record(oid, account_id, OUTCOME_KIND, now.isoformat(),
                {"outcome_id": oid, "decision_id": decision["decision_id"], **fields(ref),
                 "instrument_id": decision["instrument_id"], "horizon_sessions": horizon,
                 "entry_session": entry["timestamp"][:10], "exit_session": exit_bar["timestamp"][:10],
                 "matured_at": _available_at(exit_bar["timestamp"]).isoformat(),
                 "recorded_at": now.isoformat(), "gross_return": gross,
                 "net_return_assumed": gross-.001, "round_trip_cost_bps_assumed": 10,
                 **({'source_provenance': current_source, 'research_only': True,
                     'historical_evaluation_allowed': False} if current_source else {}),
                 "basis": "NEXT_OBSERVABLE_CLOSE_FORWARD_RETURN_NOT_STOP_TARGET_SIMULATION"})
    outcomes = [row for row in repository.paper_records(account_id, OUTCOME_KIND, as_of=now.isoformat(), limit=READ_LIMIT)
                if reference(row) == ref]
    from domain.evaluation.effectiveness import ContextualEffectivenessLearner, FeatureOutcome
    by_id = {row["decision_id"]: row for row in decisions if reference(row) == ref}
    cells, learner = {}, ContextualEffectivenessLearner()
    for horizon in HORIZONS:
        observations = []
        for row in outcomes:
            decision = by_id.get(row["decision_id"])
            if decision is None or row["horizon_sessions"] != horizon:
                continue
            for condition, state in decision["features"]["conditions"].items():
                if state is None:
                    continue
                # These are condition cohorts, NOT long/short payoff attribution.
                observations.append(FeatureOutcome(condition + ("_present" if state else "_absent"),
                    VERSION, "setup_cohort", row["instrument_id"], f"{horizon}_sessions", None, None, 1,
                    timestamp(decision["decision_at"]), timestamp(decision["features"]["available_at"]),
                    timestamp(row["matured_at"]), row["gross_return"], row["net_return_assumed"],
                    row["outcome_id"], **fields(ref)))
        cells[str(horizon)] = {}
        for feature in sorted({item.feature_id for item in observations}):
            estimate = learner.estimate(observations, feature_id=feature, instrument_id="ALL",
                horizon_id=f"{horizon}_sessions", evaluated_at=now, strategy_profile=ref)
            cells[str(horizon)][feature] = {name: getattr(estimate, name) for name in (
                "sample_count", "negative_outcomes", "expected_return_net", "uncertainty", "status", "fallback_level")}
    return {**fields(ref), "governance": "SHADOW_NOT_PROMOTED", "read_limit": READ_LIMIT,
            "condition_cohorts": cells, "minimum_samples": 30,
            "interpretation": "OBSERVATIONAL_COHORTS_NOT_CAUSAL_INDICATOR_CREDIT_OR_PROFIT_PROOF",
            "uncertainty_limit": "OVERLAPPING_SESSIONS_AND_INSTRUMENTS_NOT_INDEPENDENT_WALK_FORWARD_REQUIRED",
            "benchmark_screen": "MOMENTUM_RSI_UNCHANGED", "decision_count_in_read_window": len(decisions),
            "horizons": {str(h): {"sample_count": len(rows := [r for r in outcomes if r["horizon_sessions"] == h]),
                "negative_count": sum(r["net_return_assumed"] < 0 for r in rows),
                "mean_net_return_assumed": sum(r["net_return_assumed"] for r in rows)/len(rows) if rows else None,
                "state": "DESCRIPTIVE_ONLY_NOT_VALIDATED", "cost_basis": "10_BPS_ASSUMED_NOT_OST"} for h in HORIZONS}}
