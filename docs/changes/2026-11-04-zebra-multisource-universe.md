# Multi-instrument Zebra research flow

The ShareData collection and close comparison now cover the complete current
registered research catalog plus identity-checked retained radar discoveries.
The catalog resolves internal names to JSE symbols, including the four ETFs;
each source and instrument is handled separately. The daily local collector
refreshes the registered Yahoo universe, then the mapped ShareData universe,
retaining separate raw ShareData responses, identity-page receipts, actual
acquisition clocks and comparison results. A failed capture or comparison
retains its earlier result and does not stop other instruments.

ShareData-only technical views are separate from the original Yahoo/IRESS
handover. They begin after the most recent unresolved source conflict; the
technical endpoint selects the most recent usable source window, then the one
with the greatest feature coverage. It identifies the chosen provider and
receipt and does not combine provider fields into a fabricated full bar.

For replay, matched intact ShareData bars can continue any mapped existing
share. Other shares can use their own separate valid observed source window
when a retained Yahoo history confirms the symbol and matches recent closes.
The Satrix 40 benchmark can be extended as a close-only series after overlap
checks. An unresolved comparison divides a research replay into distinct
windows; the most recent usable window is selected and exclusion counts and
comparison times are written to replay metadata. A conflict is resolved only
when three named providers agree. Different sites may use a common upstream
feed; agreement is not proof of independent verification. Older captures and
prior frozen runs remain untouched. Dates outside the documented 2026 calendar
remain observed dates, not a certified complete exchange calendar.

On 4 November, 37 mapped ShareData captures and comparisons succeeded; the
separate full registered Yahoo refresh captured 23 of 23. The retained
comparison reported 4,987 unresolved sessions across the universe, mostly
older observations; this is not a claim that either source is wrong. The
subsequent intake discovered Datatec from its retained, identity-checked IRESS
history and captured it too: 38 mapped instruments now have ShareData views
and close comparisons. The latest intake found 32 usable share windows and a
256-session benchmark window through 3 November. Seven sample technical API
checks returned histories through 3 November, although ETF_STXIND still lacked
enough valid same-source range observations for ATR. Other mappings remain
available in the close comparison and may not yet meet full-bar replay requirements.

Research replay `ab4d3a79fa63a1173c8d9810edb65c60766ce82123fa0e1e50a625c4c58e2bab`
contained 32 shares: the Swing baseline raised 118 signals and produced 85
closed hypothetical trades. These are not validated returns or strategy skill.
A local Flask test-client pass over all 38 mapped instruments returned 29
complete technical reports and nine partial reports, with none unavailable.
Partial reports identify the missing windows or benchmark; conflicting
observations and earlier captures remain available separately.

Moneyweb SENS is connected but a dated historical price adapter has not been
verified; it is not counted as a price provider. Provider adjustment basis,
corporate actions, upstream independence and historical point-in-time
availability remain unverified. This is research-only and changes no execution,
paper, broker, or registered prospective-comparison settings.
