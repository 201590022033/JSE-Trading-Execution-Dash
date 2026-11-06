# Momentum target research comparison

`scripts/run_momentum_target_comparison.py --instrument BTI --family box`
creates a content-addressed report from the retained Zebra fields. The same
command supports any catalogued instrument with usable observed OHLC and each
existing swing, box, pull or VCP family. The Backtest Lab Momentum target
comparison panel reads the frozen report; selecting a signal shows its
calculation, outcomes and closing-price chart. Ask the Desk receives compact
matching retained comparisons as retrospective context when they fit its prompt.
Use `--horizon 3`, `--horizon 4` or `--horizon 5` to choose observed sessions.
The reference runs disable entry-volume and benchmark filters consistently for
all four variants so optional context can be compared without suppressing the
underlying signals; they are not the original fully filtered baseline.

Each signal uses the same family filters and initial stop in four independent
replays: fixed 2R, momentum, momentum with volume state, and momentum with
sector-proxy direction. Five-session price movement and change are scaled by
the trailing 14-session mean true range. Prior same-instrument daily windows
with the same momentum and acceleration signs are comparable; optional volume
or proxy variants additionally match their respective state. These are daily
market-state matches, not a claim that every historical case fired the same
strategy. Each comparison outcome has completed before the signal session.
The median subsequent favourable excursion in ATR units is converted using the
signal-date ATR and applied to the actual simulated entry. Missing optional
fields or absent/nonpositive projections fall back to 2R, explicitly labelled.

Runs have identical signal lists, but exits can change later position overlap,
capital and hence the set of trades. Excursion is not executable profit;
the replay's actual stops, costs and unknown intrabar ordering determine the
reported simulated outcomes. Costs are hypothetical, source availability is
reconstructed, and current sector proxies do not prove historical membership.
The analysis is exploratory and is separate from the registered component
learning and holdout budgets. It does not train a model, promote a strategy,
or alter the live/paper trading path. Raw source field references and code
hashes are retained with each report.
The component proposer receives a separate projection recomputed exclusively
from the training prefix at its cutoff. It does not consume the full-period
retrospective reports or use their holdout outcomes. The existing component
and cloud-call budgets still apply; adding context does not start another call.
