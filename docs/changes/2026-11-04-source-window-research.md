# Source-window research

The Technical Intelligence panel can inspect a selected instrument's retained
public zebra history through the separate read-only
`/api/v1/backtest-lab/windowed-technical/<instrument>` route. It verifies the
handover hash, instrument and actual acquisition clocks. Historical observations
are reconstructed research, not proof of point-in-time availability, a current
quote, a policy decision or a trade signal.

Each feature checks its own inputs. EMA and RSI use the uninterrupted observed
close suffix; volume uses the last 21 observed volume rows; each prior range
uses its own 10- or 20-row window; relative return requires matching benchmark
endpoints. ATR starts after the last invalid OHLC row or provider transition
and needs at least 15 valid same-source rows. The result identifies its ATR
seed and lists recent invalid sessions. Provider dates are observed dates and
do not establish a complete exchange calendar. No value is estimated or used
to repair a bad bar. The existing policy snapshot, B5 and execution gates are
unchanged.

On the locally retained 2 November Yahoo captures, NPN and ETF_STX40 returned
all requested features in a local Flask test client. Sasol returned close and
volume features but only two consecutive valid OHLC rows, so ATR and prior
ranges remain unavailable. BVT had valid prior ranges but its latest OHLC row
failed validation, leaving ATR unavailable. These are descriptive examples,
not strategy recommendations. The running Flask server must restart to serve
the new endpoint and template.

Verification: `python -m unittest test_windowed_research test_swing_technical
test_backtest_lab test_radar_etf_context test_radar_public_price_capture
test_zebra_public_handover -q` ran 29 tests successfully; `node --check
static/js/backtest-lab.js` passed.
