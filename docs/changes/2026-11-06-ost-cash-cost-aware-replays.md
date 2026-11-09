# Cash-share cost-aware replays

The target-design runner now accepts `--cost-basis ost`. It feeds the existing `OSTCashShareCosts` schedule into the complete daily replay rather than repricing existing trades: costs affect entry quantities, cash, and subsequent fills. The generic control retains its previous 8 bps fee with R60 minimum. Both arms use 20 bps assumed round-trip spread and 5 bps assumed slippage per fill. The OST arm uses the displayed account brokerage rate of 0.5% and R110 minimum before VAT, and the existing public-schedule assumptions for settlement, levy, purchase-side share tax, VAT and component rounding. The present schedule is not proof of historical rates or actual invoices; all fills and spreads remain proxies.

Both pairs share the same frozen input and current implementation hashes, R1,000,000 starting capital, 3-observed-session horizon and fixed-2R baseline. No model calls or account actions were used. The results are full-window exploratory research, not an untouched forward evaluation.

| Case | Generic signals / closed trades / net | OST signals / closed trades / net | Generic / OST max drawdown |
|---|---|---|---|
| BTI box | 100 / 73 / -R38,009.15 | 100 / 69 / -R244,721.07 | -13.02% / -27.93% |
| SASOL pull | 148 / 117 / +R25,078.45 | 148 / 111 / -R344,404.12 | -7.71% / -39.08% |

Reports (generic / OST): BTI `baed8c1fe3cb62595c3b79e9bfd21a5e9fbfcd5402e4d046829f611c98b14aae` / `befe20b2ec41c2720a0b503ccf91fc1c91aaaac685129504fa6d0c3e79e3122c`; SASOL `c2be6123c2d33daf4c4d4653b77437e08b943e1d7836b8e4104361e64f0d769f` / `1157c363f35617784198dadaa8f7542950614b668f824b32222fa87bf1f132bc`. Reports include all ten existing variants. These results do not model a R5,000 account; position sizing must be tested separately.

Commands: `.venv\\Scripts\\python.exe scripts/run_target_design.py <frozen-input> --cost-basis generic` and the same command with `--cost-basis ost`. An actual OST cash-share contract note would help verify the cost components and rounding for that particular trade, without assuming one invoice establishes historic schedules or other products. No transaction is needed to run this research.
