"""Exact-version registry with explicitly selected current versions, never overwrite."""
from types import MappingProxyType
from dataclasses import replace
from .profile import CapabilityState as C, StrategyCapability as Capability
from .profile import StrategyLifecycle as L, StrategyProfile, StrategyProfileRef


class StrategyProfileRegistry:
    def __init__(self, profiles, *, current_versions, research_profiles=()):
        index = {}
        for profile in profiles:
            if not isinstance(profile, StrategyProfile):
                raise TypeError("typed strategy profile required")
            key = (profile.reference.strategy_profile_id, profile.reference.strategy_profile_version)
            if key in index:
                raise ValueError("strategy profile versions cannot be overwritten")
            index[key] = profile
        current = dict(current_versions)
        if set(current) != {key[0] for key in index} or any((key, version) not in index for key, version in current.items()):
            raise ValueError("every strategy must pin an existing current version")
        # Lab-only profiles resolve through the same registry without adding
        # experimental cards to the existing operational profile listing.
        research = {}
        for profile in research_profiles:
            if not isinstance(profile, StrategyProfile):
                raise TypeError("typed strategy profile required")
            key = (profile.reference.strategy_profile_id, profile.reference.strategy_profile_version)
            if key in index or key[0] in current or key[0] in research:
                raise ValueError("research profile identity must be distinct")
            index[key] = profile
            research[key[0]] = key[1]
        self._research = MappingProxyType(research)
        self._profiles = MappingProxyType(index)
        self._current = MappingProxyType(current)

    def resolve(self, strategy_profile_id, strategy_profile_version=None):
        version = strategy_profile_version if strategy_profile_version is not None else (self._current.get(strategy_profile_id) or self._research[strategy_profile_id])
        return self._profiles[(strategy_profile_id, version)]

    def current_profiles(self):
        return tuple(self.resolve(key) for key in self._current)

    def versions(self, strategy_profile_id):
        if strategy_profile_id not in self._current and strategy_profile_id not in self._research:
            raise KeyError(strategy_profile_id)
        return tuple(profile for (key, _), profile in self._profiles.items() if key == strategy_profile_id)


def default_profiles():
    return (
        StrategyProfile(StrategyProfileRef("jse_swing_3_5d", "1.0.0"), "JSE Swing Trader — 3–5 Day",
            "Swing Trader", "3–5 Day", L.ACTIVE_RESEARCH_PAPER, "jse_cash_swing",
            ("JSE_CASH_EQUITIES",), "1d", ("3_sessions", "4_sessions", "5_sessions"),
            ("RESEARCH", "SHADOW", "PAPER"), (
                Capability("canonical_research", C.IMPLEMENTED_REUSABLE,
                    "Existing daily canonical screening and ranking; no new strategy ranker.",
                    ("application.opportunities.public_research", "domain.evaluation.opportunity")),
                Capability("context_and_news", C.IMPLEMENTED_REUSABLE,
                    "Existing technical, regime, divergence and causal news inputs; sentiment is opinion, not a validated catalyst model.",
                    ("domain.registry.feature", "domain.features.regime", "domain.features.divergence", "application.opportunities.news_ingestion")),
                Capability("paper_and_risk", C.IMPLEMENTED_REUSABLE,
                    "Existing daily-close, long-only, three-session paper simulator and risk veto; not actual OST account sizing.",
                    ("domain.policy.paper_geometry", "domain.risk.paper_sizing", "application.opportunities.paper_loop", "domain.broker.paper")),
                Capability("profile_attribution", C.PLANNED,
                    "Exact profile attribution through opportunity, policy, risk, paper and learning records is not yet wired."),
                Capability("swing_evidence", C.IMPLEMENTED_REUSABLE,
                    "Compact three/four-session Yahoo setup context and M11 learner; descriptive shadow evidence only.",
                    ("application.opportunities.swing_history", "domain.evaluation.effectiveness")),
                Capability("entry_refinement_30m", C.BLOCKED,
                    "30-minute chart display exists; validated session/data/cost contracts for swing entry refinement remain missing.",
                    ("domain.market_data.horizons", "jse_adapter")),
            ), ("Foundation links an existing workflow; its records are not yet produced by this StrategyProfile.",
                "Current ranking evidence is one-day; paper holding is three sessions. The intended 3–5-session scope does not change either.",
                "Curated cash universe is not certified liquid; explicit liquidity admission remains required.",
                "Actual OST fees, cash and spread remain unconfigured. Research rank is separate from account feasibility.",
                "ETFs retain their existing separate research path; this initial profile targets cash equities.",
                "No validated profitability, automatic promotion or broker execution."), "canonical-opportunities"),
        StrategyProfile(StrategyProfileRef("intraday_cfd", "1.0.0"), "Intraday CFD", "Intraday CFD", "5–60 min",
            L.DEVELOPMENT_DATA_VALIDATION_REQUIRED, "intraday_cfd", ("CFD_CONTRACTS",),
            "INTRADAY_NOT_CONFIGURED", ("intraday_5m", "intraday_15m", "intraday_30m", "intraday_60m", "intraday_eod"),
            ("RESEARCH",), (
                Capability("hr11_causal_core", C.IMPLEMENTED_REUSABLE,
                    "HR11 horizon/session/aggregation/evaluation infrastructure exists; it is not an admitted intraday strategy.",
                    ("domain.market_data.horizons", "intraday_evaluation", "hr11_research")),
                Capability("broker_data_boundary", C.IMPLEMENTED_REUSABLE,
                    "Read-only IG discovery/history and gated Demo safety components exist; this profile activates none.",
                    ("domain.broker.ig", "domain.broker.ig_history", "domain.broker.execution_safety")),
                Capability("intraday_strategy", C.BLOCKED,
                    "Verified real-data depth, contract/session/cost evidence, walk-forward validation and attribution are required."),
            ), ("No validated intraday strategy, profile ranking or execution workflow.",
                "Public CFD reference charts are not broker contract prices.",
                "IG Demo submission remains disabled and requires separate explicit permission; LIVE is prohibited.")),
        StrategyProfile(StrategyProfileRef("long_term_investment", "1.0.0"), "Long-Term Investment",
            "Long-Term Investment", "Weeks–Months", L.DEVELOPMENT, "long_term_investment",
            ("INVESTMENT_UNIVERSE_NOT_CONFIGURED",), "NOT_CONFIGURED", ("weeks", "months", "longer"),
            ("RESEARCH",), (
                Capability("market_intelligence", C.IMPLEMENTED_REUSABLE,
                    "Existing source/provenance and market-intelligence boundaries can be reused for investigation.",
                    ("domain.registry.source", "market_intelligence")),
                Capability("investment_model", C.PLANNED,
                    "Fundamentals, valuation, balance sheet/earnings, macro/sector context and slower trends need separate data and evaluation contracts."),
            ), ("No investment ranking, validated model, account sizing or execution workflow.",
                "Weeks/months are intended horizons, not executable horizon contracts.",
                "Swing technical rules are not reused as an investment strategy.")),
    )


_defaults = default_profiles()
# Preserve the shipped 1.0.0 definition exactly. Attribution is an additive
# version, not evidence that the intended Swing rules have been validated.
_attributed_swing = replace(_defaults[0], reference=StrategyProfileRef("jse_swing_3_5d", "1.0.1"),
    capabilities=tuple(replace(item, state=C.IMPLEMENTED_REUSABLE,
        description="Exact-version lineage for new canonical runs and paper learning; legacy records stay unattributed.",
        component_references=("domain.strategy.attribution", "application.opportunities.paper_loop", "persistence.paper_ledger"))
        if item.capability_id == "profile_attribution" else item for item in _defaults[0].capabilities),
    limitations=("New canonical runs retain this exact profile; older jobs and records remain LEGACY_UNATTRIBUTED.",
                 *_defaults[0].limitations[1:]))
_technical_swing = replace(_attributed_swing,
    reference=StrategyProfileRef("jse_swing_3_5d", "1.1.0"),
    universe_scope=("JSE_CASH_EQUITIES", "JSE_INDEX_ETFS"),
    capabilities=(*_attributed_swing.capabilities,
        Capability("swing_technical_horizons", C.IMPLEMENTED_REUSABLE,
            "Separate OHLCV EMA20/50, Wilder RSI/ATR14 and independent 3/4/5-session forward-return shadow path. Not the benchmark ranker or paper execution policy.",
            ("application.opportunities.swing_technical",))),
    limitations=("Separate technical shadow version; current benchmark stays pinned to 1.0.1.",
        "Close-return labels are not stop/target execution, causal indicator attribution or validated profitability.",
        "Sector alignment, catalysts/calendar, ATR execution geometry, trailing and actual OST costs remain gates.",
        "Curated cash and index ETF research scope is not certified liquid or admitted for execution.",
        "Actual OST cash, fees and spreads remain unconfigured; no validated profitability or broker execution."))
_policy_swing = replace(_technical_swing,
    reference=StrategyProfileRef("jse_swing_3_5d", "1.2.0"),
    universe_scope=("JSE_CASH_EQUITIES",),
    allowed_research_modes=("RESEARCH", "SHADOW"),
    capabilities=(*_technical_swing.capabilities,
        Capability("daily_shadow_policy", C.IMPLEMENTED_REUSABLE,
            "Separate cash LONG shadow: first later observable close within seven calendar days; fixed structural/ATR stop, entry-based 2R target, no trailing, 3/4/5 observed-session exits; conservative daily OHLC replay and hypothetical 10/25/50 bps costs. No orders or risk approval.",
            ("domain.policy.swing_shadow", "application.opportunities.swing_policy"))),
    limitations=("Shadow policy version only; current ranking and paper benchmark stay pinned to 1.0.1.",
        "Completed-close proxy and daily OHLC replay are hypotheses, not actual broker fills or validated profitability.",
        "Liquidity, verified exchange calendar, sector/catalysts, corporate-action quality and actual OST costs/account feasibility remain unresolved; M15 approval is not granted.",
        "Overlapping per-signal horizons are research samples, not an executable portfolio or walk-forward proof.",
        "ETFs retain separate 1.1.0 technical research; no ETF policy or trading admission."))
_research_swing = replace(_policy_swing,
    reference=StrategyProfileRef("jse_swing_3_5d", "1.3.0"),
    capabilities=(*_policy_swing.capabilities,
        Capability("ai_hypothesis_research", C.IMPLEMENTED_REUSABLE,
            "Local daily raw history and authenticated cloud snapshots; bounded Ollama hypotheses for volume, RSI ceiling and 3/4/5-session exits, frozen proposals and chronological historical comparisons. No automatic promotion or execution.",
            ("application.opportunities.swing_research", "scripts.collect_swing_data"))),
    limitations=("Research-loop version; canonical ranking/paper benchmark remains pinned to 1.0.1.",
        "Historical comparisons are not prospective walk-forward validation or executable portfolio evidence.",
        "Local collector requires a powered-on signed-in computer; incomplete source data stays blocked.",
        *_policy_swing.limitations[1:]))
_lab_profiles = tuple(StrategyProfile(StrategyProfileRef(identity, "1.0.0"), name, name, "3 sessions",
    L.DEVELOPMENT_DATA_VALIDATION_REQUIRED, identity, ("JSE_CASH_EQUITIES",), "1d", ("3_sessions",),
    ("RESEARCH",), (Capability("daily_approximation", C.IMPLEMENTED_REUSABLE,
        "Unvalidated daily-bar approximation with hypothetical fixed-horizon/2R exits.", ("application.backtest_lab.strategies",)),),
    ("Thresholds are guesses; this is not the original intraday setup.", "No validated profitability or execution authority."))
    for identity,name in (("vcp_daily_research", "VCP daily approximation"),
                          ("box_breakout_daily_research", "Box breakout daily approximation"),
                          ("pullback_daily_research", "Pullback daily approximation")))
DEFAULT_STRATEGY_REGISTRY = StrategyProfileRegistry((*_defaults, _attributed_swing, _technical_swing, _policy_swing, _research_swing), research_profiles=_lab_profiles, current_versions={
    **{profile.reference.strategy_profile_id: profile.reference.strategy_profile_version for profile in _defaults},
    "jse_swing_3_5d": "1.0.1"})
