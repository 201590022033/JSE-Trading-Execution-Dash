# ADR 0092: Separate historical handover and radar public prices

30 October 2026. Existing current-input freshness policies removed entire
charts from current technical and worker views. A research-only, content-hashed
handover exposes retained zebra closes without treating them as current prices.
It does not modify frozen research panels, decisions, model budgets or trading
inputs. The existing daily collector independently captures bounded public
Yahoo price histories for explicitly linked, registered radar issuers, reusing
the existing Yahoo chart normalizer and isolating failures per issuer.

The handover preserves source lineage and reconstructed clocks; public captures
retain normalized observations and actual acquisition times, not raw Yahoo
HTTP bytes. Provider finality and adjustments are not certified. Current
worker freshness and prospective endpoint contracts remain unchanged. No
automatic provider fusion, broker login or trade is introduced. Revert by
removing the handover and radar capture hooks from the collector and dashboard;
retained source data and earlier evidence do not need to be changed.
