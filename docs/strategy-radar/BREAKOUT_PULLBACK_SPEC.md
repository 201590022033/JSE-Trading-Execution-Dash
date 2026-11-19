# Breakout and pullback research specification

**Candidate:** breakout_pullback_daily_research v1.0.0. The owner confirmed the starting parameters on 19 November 2026. These are editable research assumptions. Their predictive value and calibration are untested.

## 1. What exists today

- **Daily v1.1.2.** The profile picks a three-session EMA20 reclaim lookback and the prior-20 median volume ratio, with a mean fallback when the median is zero. A reclaim is a close crossing from at/below its own EMA20 to above the next EMA20, with the current close still above EMA20 above EMA50. A breakout compares the latest completed close strictly against the highest high of the preceding 20 observations. The snapshot's core_setup combines trend, breakout or reclaim, inclusive Wilder RSI14 from 50 to 70, volume ratio strictly above 1 and 20-session benchmark excess return strictly above zero. It is unavailable if required calculations or valid shadow stop geometry are missing. [Feature contracts and reclaim](../../application/opportunities/swing_technical.py#L17-L38) · [Snapshot and conjunction](../../application/opportunities/swing_technical.py#L86-L171)
- **Radar presentation.** The selected watch supplies Zebra-selected daily evidence and a cached benchmark aligned to its target session. The Radar applies component-specific windows, assembles individual traces, counts pass and unknown rows and returns its evaluation and calculation clocks, session, source hash, benchmark status and data quality. Its aggregate state is WATCHING or UNKNOWN. The checklist is a display of evidence, so its component eligibility can differ from core_setup. [Component windows and payload](../../application/strategy_radar/swing_radar.py#L140-L228)
- **Existing pull family.** The registry names pullback_daily_research v1.0.0 “Pullback daily approximation.” Its rule labels are “EMA9 above EMA21 and EMA21 rising over five bars,” “Prior close 1–7% below earlier high,” “Close above prior high,” and “Volume at least 1.1× prior average.” The earlier high excludes the last two bars. The stop is the minimum of the last four lows and must be positive and below the signal close. The legacy evaluator traces provider continuity. Lab variants can disable the pullback condition with trigger_only, disable both pullback and trigger with trend_only, or omit the volume gate explicitly. This geometry measures a short recovery from a decline. It stores no breakout event or frozen retest level. [Registry](../../domain/strategy/registry.py#L176-L184) · [Pull rules](../../application/backtest_lab/strategies.py#L70-L83) · [Component modes](../../application/backtest_lab/components.py#L37-L50) · [Price-only parity and rule selection](../../application/backtest_lab/components.py#L59-L138)
- **Replay and exits.** Signals reserve capital at decision time and are considered for the first later observable completed close. The engine applies costs and adapter sizing, rejects expired, unfinanceable or pre-close-invalidated entries, and uses the cost-adjusted fill for R and target. The entry session counts as zero held. An opening stop gap exits at the open and a target gap fills at the target limit. When both levels are touched after the open and ordering is unknown, the stop goes first. An explicitly configured EMA21_CLOSE exits at the close crossing against the position, ahead of the horizon check. Unclosed positions stay marked at the data cutoff. [Replay admission](../../domain/backtest/component_engine.py#L136-L178) · [Exit and fill order](../../domain/backtest/component_engine.py#L248-L303)
- **Five-minute profile.** It requires four contiguous completed bars in one verified open JSE session, with a recent latest bar. Mandatory checks are latest close above prior bar high plus any configured daily-close gate, latest close above the preceding three closes' mean, and latest close above the preceding close. Supplemental checks are volume at least 1.2 times its prior-three-bar mean and excess return versus exactly aligned benchmark intervals. All mandatory passes yield ENTRY_MET. Otherwise the developing fraction of 0.8 requires four passes, all unknown yields UNKNOWN, and remaining cases are WATCHING. Its separate research geometry uses a 2% stop, 2R target and three-bar exit. [Five-minute evaluator](../../application/strategy_radar/intraday_evaluation.py#L132-L223)
- **Daily and five-minute fields.** Both snapshot paths expose RSI as rsi, EMA as ema_fast/ema_slow/ema_spread, fast stochastic as stochastic_k/stochastic_d, and smoothed stochastic as slow_k/slow_d. Ichimoku includes tenkan, kijun, current_senkou_a/current_senkou_b, future_senkou_a_known_at_t/future_senkou_b_known_at_t, price_cloud_state and the registry's other cloud/TK/Chikou outputs. Required contiguous suffixes are respectively 15, 26, 16, 18 and 78 bars, with a 300-bar cap. Each suffix ends at the newest visible completed bar and stops at a gap or missing required field. Daily inputs use selected Zebra values with acquisition clocks at or before as_of. Five-minute inputs exclude provisional bars. Missing fields are preserved, including OST's absent Open. ATR is absent from this snapshot. The swing snapshot has Wilder ATR, while the technical registry's existing ATR is mean true range. [Indicator inputs and output](../../application/strategy_radar/intraday_indicators.py#L22-L129) · [Registry and cloud outputs](../../technical_feature_registry.py#L125-L176) · [Swing Wilder ATR](../../application/opportunities/swing_technical.py#L101-L114)

### What the hypothesis families measure

| Family | Proposed comparison | What retained coverage can establish |
| --- | --- | --- |
| H1 selected shares | Continuation breakout vs reclaim | Configured SASOL, BTI, FSR and ABSPJ swing examples used v1.3.0 breakout_or_reclaim. The BTI box and SASOL pull examples are included in this group. |
| H2 resources | Breakout/reclaim with matched commodity and FX context | SASOL swing v1.3.0 breakout_or_reclaim and pull v1.0.0 family_default. |
| H3 industrial/global | Breakout/reclaim with a business-specific driver and peer strength | BTI swing v1.3.0 breakout_or_reclaim and box v1.0.0 family_default. |
| H4 banks/financials | Post-shock recovery vs reclaim | FSR and configured ABSPJ swing artifacts used v1.3.0 breakout_or_reclaim. |
| H5 USD/ZAR | Directional range breakout/retest | The separate retained price-only study compares 20-session and 10-session range-entry lookbacks with no broker costs. |
| H6 gold | Range breakout/retest with gold and FX context | The NEWGOLD component example used swing v1.3.0 breakout_or_reclaim. The Lab tracks listed-vehicle runs separately from spot/futures reference captures. |

The observed modes above come from SHA-256-verified artifacts referenced by the local runtime/local-backtest/component-learning reports and the FX study 0390be4160. Some ABSPJ artifacts omit the component configuration, so the table counts the modes explicitly encoded in the remainder. Coverage groups examples by ticker without assigning a chosen mode per sector. The Lab exposes breakout, reclaim and trend_only for swing, and family_default, trigger_only and trend_only for box, pull and VCP. Read each exact saved configuration before interpreting a result. [Proposed six-family entry matrix](../research/SWING_RULE_REFINEMENT.md#L73-L82) · [Coverage rules](../../application/backtest_lab/hypothesis_coverage.py#L6-L75) · [Entry modes](../../application/backtest_lab/components.py#L15-L50) · [Learning comparisons](../../application/backtest_lab/learning_loop.py#L16-L64)

## 2. Candidate definition

| Parameter | Starting value |
| --- | --- |
| N_BREAKOUT | 20 observed completed sessions |
| W_PULLBACK | 5 observed completed sessions following breakout |
| ATR_PERIOD, PB_TOUCH_ATR, PB_BUFFER_ATR | 14, 0.5, 0.5 |
| PB_TOUCH_PCT, PB_BUFFER_PCT | 1.0%, 1.5%, a separate comparison variant |
| RSI_PERIOD, RSI_MIN, RSI_MAX | Wilder 14, 50, 70 inclusive |
| N_VOLUME, VOL_MIN | 20 prior observed sessions, 1.0 inclusive |
| BENCHMARK_LOOKBACK, MIN_EXCESS_RETURN | 20 prior observed sessions, 0 exclusive |
| STOP_ATR_BUFFER, TARGET_R | 0.25, 2.0 |
| HOLD_MIN, HOLD_MAX | 3 and 5 completed post-entry sessions, each configured horizon tested independently |
| MAX_ACTIVE, MAX_GAP_SESSIONS, MIN_BARS | 1 per instrument, 3 missing exchange sessions, 10 observed completed bars |

Use only completed bars and fields available at the decision clock. A close strictly above the highest high of the prior N_BREAKOUT sessions creates a breakout. Freeze breakout_level (that high), breakout_date and breakout_bar_high (the breakout session's own high). Insufficient highs make the breakout rule NO_DATA. Record the breakout even when its own RSI exceeds RSI_MAX. Begin counting the pullback window on the next observed completed session.

For the ATR variant, a touch is an absolute distance from the session low of at most PB_TOUCH_ATR times its point-in-time Wilder ATR to either the frozen breakout level or the **current displaced cloud top**, max(current_senkou_a, current_senkou_b). Record which level was touched, or both. Invalidation uses only breakout_level less PB_BUFFER_ATR times the current session ATR. A close strictly below the floor invalidates the setup, even after a touch. For the percentage comparison, apply PB_TOUCH_PCT to the tested level and PB_BUFFER_PCT to the frozen breakout level. The variant still uses Wilder ATR for stop geometry. Cloud unavailability leaves the frozen-level route evaluable. A missing floor cannot be recorded as held.

After an earlier valid pullback, test for a close strictly above the previous observed session high, Wilder RSI in range, Zebra selected volume at or above VOL_MIN times its own prior N_VOLUME median, close above the current displaced Ichimoku cloud top, and a strictly positive aligned benchmark excess return. Match the instrument and benchmark at both ends of the same N-session interval with the current watch benchmark and no forward fill. Sequence, sufficient history, and an observed structural hold are necessary to establish a setup and retest. Once those exist, any available trigger failure prevents triggering. Unavailable optional evidence, including RSI, cloud, volume and benchmark, remains NO_DATA and is skipped. An unavailable previous high produces NO_DATA for the resumption event, so the state stays in the pullback zone. Record each rule state and the number evaluable. The prior median must be positive. The mean fallback in daily v1.1.2 remains isolated from this candidate. Recompute each alternative provider's ratio from its own visible current and prior values and report any threshold flip for information only. The Zebra audit's median ShareData uplift versus EODHD was 6.6%, with 12 flips in 119 VOD evaluations. That observation is source sensitivity evidence. [Zebra audit](../roadmap/POST_R18_ZEBRA_AUDIT_2026-11-19.md)

At trigger, freeze the lowest observable low across the pullback through the trigger session, excluding the breakout bar, and subtract STOP_ATR_BUFFER times trigger-session Wilder ATR for the stop reference. Show the close-based TARGET_R reference and breakout-bar high separately. Freeze the retrospective engine stop and use the engine's actual hypothetical fill to calculate its TARGET_R level. If stop geometry is missing or invalid, keep the trigger as an observation with no replayable order.

Run on the observed session sequence. Gaps up to MAX_GAP_SESSIONS keep the setup eligible and are labelled GAP_TOLERATED, with gap clocks attached. For a longer gap the working spec retains the setup, labels it PARTIAL and leaves checks that require the unobserved segment NO_DATA. A prefix from MIN_BARS to the breakout span evaluates available inputs with a low-confidence label. Full-window checks stay NO_DATA until their own warmup is met. Below MIN_BARS show NO_DATA for the setup calculation and stay WATCHING. Retain CONFIRMED, PARTIAL, GAP_TOLERATED or SINGLE_SOURCE coverage with source IDs, alternatives and clocks. Missing Open is never estimated. Report replay coverage separately when the engine cannot admit a native OHLC execution window.

## 3. Weighted score

The weights are starting assumptions. Score each evaluable component in the range from zero to one. Clip linear ratios to that interval. Report the component values and evaluable count. Divide the weighted sum by the sum of the evaluable weights, then scale to 0–100. If no component is evaluable, the rank is NO_DATA. Compare the same components with equal weights. The score ranks setups. Probability language requires separate outcome calibration.

| Editable weight | Initial value | Candidate component, evaluated at decision time |
| --- | ---: | --- |
| WT_STRUCTURE | 35% | Zero following invalidation. With valid hold and a measured retest, one minus the minimum distance to an eligible level divided by its touch tolerance. |
| WT_TREND | 20% | Mean of two binary observations when both cloud tops exist. Close above current cloud top, and current cloud top above the prior observed session's cloud top. |
| WT_MOMENTUM | 20% | Mean of two binary observations. Minimum pullback RSI below breakout RSI, and current RSI above prior RSI with current RSI in range. |
| WT_VOLUME | 15% | Mean of two binary observations on selected volume. Minimum pullback-session ratio below VOL_MIN, and current ratio at least VOL_MIN and above the preceding session's ratio. |
| WT_RELATIVE | 10% | Clip positive benchmark excess return divided by RELATIVE_SCORE_SCALE. Starting scale is 5 percentage points over the benchmark window. |

A component with incomplete inputs is NO_DATA. Report categorical evidence and score inputs alongside the rank. RELATIVE_SCORE_SCALE and the scoring functions are proposed W02 operational choices. Freeze them before W06 alongside the owner-confirmed starting parameters.

## 4. State machine on observed daily closes

| From | Condition, evaluated in order | To |
| --- | --- | --- |
| WATCHING | Close strictly exceeds the prior N_BREAKOUT high with full high coverage | BREAKOUT_SEEN |
| BREAKOUT_SEEN or IN_PULLBACK_ZONE | In-window close breaches the applicable floor | INVALIDATED |
| BREAKOUT_SEEN | In-window session touches an eligible level and the same observed close holds the floor | IN_PULLBACK_ZONE |
| IN_PULLBACK_ZONE | A subsequent in-window close passes the resumption event and all evaluable trigger filters | TRIGGERED |
| BREAKOUT_SEEN or IN_PULLBACK_ZONE | Last observed window slot completes with no trigger or invalidation | EXPIRED |

Otherwise keep the current state. Ignore new breakouts while one setup is active. On the final slot, invalidation and trigger take precedence over expiry. A first touch on that slot alone expires because a subsequent session is required. Keep the terminal state in the per-session result. Begin looking for a fresh breakout on the next observed completed session. Report frozen setup fields, observed window count and remaining slots, last session, pullback low, rule states and score. A projected calendar end is an estimate when sessions may be missing.

### Illustrative completed-bar sequence

All prices and indicator values below are made up. Assume complete warmup and ATR14 of R2 each session.

| Session | Observations | Result |
| --- | --- | --- |
| T | Prior high R100, close R103, high R104, RSI 79 | BREAKOUT_SEEN. Freeze R100, with R104 as comparison high. |
| T+1 | Low R101.60, close R102, cloud top R100.20, RSI 70 | BREAKOUT_SEEN. The low is beyond both R1 touch bands. |
| T+2 | Low R100.40, high R102.50, close R101, RSI 62 | IN_PULLBACK_ZONE. Touches the R100 band and holds above the R99 floor. |
| T+3 | Low R101, close R103, RSI 64, volume ratio 1.2, cloud top R100.50, excess return +2 percentage points | TRIGGERED. Stop reference R99.90 and close-based target R109.20. The replay engine calculates its target from the actual hypothetical fill. |

> Daily completed-bar research. The rank has no established predictive calibration or authority to place orders. The five-minute profile runs separately.

### Integration details to preserve

- The current indicator snapshot stops at any contiguous break. W05 needs an isolated gap-tolerant use of the existing calculations, with native required fields and the existing callers' strict windows preserved. Its Wilder ATR must use the existing Wilder calculation, since the mean-ATR registry output uses a different convention.
- The active snapshot checks real OHLC for several geometry fields. This spec uses available retained fields at the observation layer and requires independently valid execution evidence wherever the engine needs Open or gap ordering.
- Radar can show newer diagnostic component rows without an eligible full daily conjunction. Comparison reports should use exact profile and artifact identity alongside rule-level coverage rather than infer an exact strategy result from the display count.
