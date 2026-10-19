"""Offline data-operations contracts with a bounded in-memory immutable ledger."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch

from application.opportunities import research_data_requests as requests
from application.opportunities.public_research import public_share_catalog, _identities
from application.opportunities.swing_research import ACCOUNT as DATASET_ACCOUNT

NOW = datetime(2026, 10, 19, 6, tzinfo=timezone.utc)  # Monday 08:00 SAST.
PAPER_ACCOUNT = "test-canonical-paper"


class MemoryLedger:
    backend = "sqlite"

    def __init__(self):
        self.accounts, self.saved = {}, {}
        self.forbid_writes = False

    @contextmanager
    def transaction(self):
        yield

    def create_paper_account(self, account_id, initial):
        if self.forbid_writes:
            raise AssertionError("Read-only status initialized storage")
        self.accounts.setdefault(account_id, deepcopy(initial))

    def paper_account(self, account_id):
        return deepcopy(self.accounts.get(account_id))

    def save_paper_record(self, rid, account, kind, available_at, payload):
        if self.forbid_writes:
            raise AssertionError("Read-only status persisted a record")
        value = (account, kind, available_at, deepcopy(payload))
        if rid in self.saved and self.saved[rid] != value:
            raise ValueError("Immutable conflict")
        self.saved[rid] = value

    def paper_record(self, rid):
        return deepcopy(self.saved[rid][3]) if rid in self.saved else None

    def paper_records(self, account, kind, *, as_of, limit=400):
        rows = [(at, rid, payload) for rid, (owner, category, at, payload) in self.saved.items()
                if owner == account and category == kind and at <= as_of]
        return [deepcopy(payload) for _, _, payload in sorted(rows, reverse=True)[:limit]]


class ResearchDataRequestTests(unittest.TestCase):
    def setUp(self):
        self.repo = MemoryLedger()
        self.shares = public_share_catalog()
        configuration = patch.object(requests, "_configuration", return_value=(PAPER_ACCOUNT, 345600))
        configuration.start()
        self.addCleanup(configuration.stop)

    def ranking(self, keys, rid="ranking-a", *, evaluated=NOW, unavailable=None):
        rows = [{"instrument_id": _identities(key, self.shares[key])[0].instrument_id, "rank": index}
                for index, key in enumerate(keys, 1)]
        snapshot = {"version": "canonical-paper-loop-v2", "mode": "PAPER", "evaluated_at": evaluated.isoformat(),
                    "strategy_profile_id": "jse_swing_3_5d", "strategy_profile_version": "1.0.1",
                    "opportunities": rows, "etf_opportunities": [{"instrument_id": "ETF_STX40", "rank": 1}],
                    "unavailable": unavailable or []}
        self.repo.create_paper_account(PAPER_ACCOUNT, {"mode": "PAPER"})
        self.repo.accounts[PAPER_ACCOUNT]["ranking_record_id"] = rid
        self.repo.save_paper_record(rid, PAPER_ACCOUNT, "ranking", evaluated.isoformat(), snapshot)
        return snapshot

    def chart(self, key, provider, *, acquired=NOW, session="2026-10-16", previous="2026-10-15"):
        code = requests.catalog()[key]["ost_code"]
        bars = [{"timestamp": day, "open": 10.0 if provider == "IRESS" else None,
                 "high": 12.0, "low": 9.0, "close": 11.0, "volume": 1000}
                for day in (previous, session)]
        return {"symbol": requests.catalog()[key]["symbol"], "currency": "ZAR", "interval": "1d", "bars": bars,
                "provenance": {"provider": provider, "origin_symbol": code+".JSE" if provider == "IRESS" else code,
                    "source_sha256": ("b" if provider == "IRESS" else "a")*64,
                    "acquired_at": acquired.isoformat(), "price_basis": "UNVERIFIED", "volume_basis": "UNVERIFIED",
                    "historical_availability": "UNVERIFIED"}}

    def dataset(self, *, acquired=NOW, session="2026-10-16", previous="2026-10-15"):
        data = {"schema": "local-swing-dataset-v3", "observed_at": NOW.isoformat(),
                "charts": {key: self.chart(key, "OST", acquired=acquired, session=session, previous=previous)
                           for key in ("SASOL", "ETF_STX40")},
                "research_charts": {"SASOL": self.chart("SASOL", "IRESS", acquired=acquired, session=session, previous=previous)}}
        self.store_dataset(data)
        return data

    def store_dataset(self, data):
        rid = "dataset-"+requests._hash(data)
        self.repo.accounts[DATASET_ACCOUNT] = {"mode": "PAPER", "latest_dataset": rid}
        self.repo.save_paper_record(rid, DATASET_ACCOUNT, "research-dataset", NOW.isoformat(), data)

    def status(self, now=NOW):
        return requests.status(self.repo, now, account_id=PAPER_ACCOUNT)

    def sync(self, now=NOW):
        return requests.sync_requests(self.repo, now, account_id=PAPER_ACCOUNT)

    def records(self, kind):
        return self.repo.paper_records(requests.ACCOUNT, kind, as_of=(NOW+timedelta(days=100)).isoformat())

    def test_exact_published_cash_ranks_map_to_registered_catalog(self):
        self.ranking(["NPN", "SASOL", "FSR", "CFR", "GFI", "VOD"])
        observed = requests.membership(self.repo, NOW, account_id=PAPER_ACCOUNT)
        self.assertEqual(observed["members"], ["NPN", "SASOL", "FSR", "CFR", "GFI"])
        self.assertEqual(observed["ranking_record_id"], "ranking-a")
        self.assertEqual(observed["ranking_sha256"], requests._hash(self.repo.paper_record("ranking-a")))
        self.assertNotIn("ETF_STX40", observed["members"])

    def test_membership_retains_exact_frozen_strategy_lineage(self):
        self.ranking(["SASOL"])
        self.sync()
        saved = self.records("data-membership")[0]
        self.assertEqual(saved["strategy_profile_id"], "jse_swing_3_5d")
        self.assertEqual(saved["strategy_profile_version"], "1.0.1")

    def test_unregistered_or_duplicate_rank_identity_fails_closed(self):
        snapshot = self.ranking(["SASOL", "NPN"])
        for value in ("UNKNOWN-CANONICAL-ID", snapshot["opportunities"][0]["instrument_id"]):
            changed = deepcopy(snapshot)
            changed["opportunities"][1]["instrument_id"] = value
            self.repo.saved["ranking-a"] = (PAPER_ACCOUNT, "ranking", NOW.isoformat(), changed)
            with self.assertRaises(ValueError):
                requests.membership(self.repo, NOW, account_id=PAPER_ACCOUNT)

    def test_membership_churn_reuses_requests_and_retains_departed_candidate(self):
        self.ranking(["SASOL", "NPN"])
        self.sync()
        initial = {r["record_id"] for r in self.records("data-request")}
        self.ranking(["SASOL", "FSR"], "ranking-b", evaluated=NOW+timedelta(minutes=1))
        changed = self.sync(NOW+timedelta(minutes=1))
        history = max(self.records("data-membership"), key=lambda r: r["received_at"])
        self.assertEqual(history["entered"], ["FSR"])
        self.assertEqual(history["left"], ["NPN"])
        self.assertTrue(history["prior_data_retained"])
        self.assertTrue(initial.issubset({r["record_id"] for r in self.records("data-request")}))
        self.assertIn("NPN", {r["instrument_id"] for r in changed["requests"]})
        self.ranking(["SASOL", "NPN"], "ranking-c", evaluated=NOW+timedelta(minutes=2))
        self.sync(NOW+timedelta(minutes=2))
        for key in ("NPN", "FSR", "SASOL"):
            self.assertEqual(sum(r["instrument_id"] == key for r in self.records("data-request")), 4)

    def test_repeat_clock_is_idempotent_not_another_membership_or_request(self):
        self.ranking(["SASOL", "NPN"])
        self.sync()
        first = deepcopy(self.repo.saved)
        self.sync(NOW+timedelta(minutes=5))
        self.assertEqual(first, self.repo.saved)
        self.assertEqual(len(self.records("data-routine")), 1)

    def test_stale_missing_and_partial_ranking_do_not_retire_saved_members(self):
        self.ranking(["SASOL", "NPN"])
        self.sync()
        original_ids = set(self.repo.saved)
        self.repo.accounts[PAPER_ACCOUNT]["ranking_record_id"] = None
        missing = self.sync(NOW+timedelta(minutes=1))
        self.assertEqual(missing["current_members"], ["NPN", "SASOL"])
        self.ranking([], "stale-ranking", evaluated=NOW-timedelta(days=5))
        stale = self.sync(NOW+timedelta(minutes=2))
        self.assertEqual(stale["membership"]["state"], "STALE_FROZEN_TOP5")
        self.assertEqual(stale["current_members"], ["NPN", "SASOL"])
        self.ranking([], "partial-ranking", evaluated=NOW+timedelta(minutes=3), unavailable=["SASOL", "NPN"])
        partial = self.sync(NOW+timedelta(minutes=3))
        self.assertEqual(partial["current_members"], ["NPN", "SASOL"])
        self.assertEqual(len(self.records("data-membership")), 1)
        self.assertTrue(original_ids.issubset(self.repo.saved))

    def test_missing_worker_never_computes_an_improvised_ranking(self):
        with patch("requests.get", side_effect=AssertionError("provider")), patch("requests.post", side_effect=AssertionError("provider")):
            state = self.status()
        self.assertEqual(state["membership"]["state"], "NO_FROZEN_TOP5")
        self.assertEqual(state["current_members"], [])
        self.assertFalse(state["automatic_download"])

    def test_malformed_missing_opportunities_cannot_retire_membership(self):
        self.ranking(["SASOL", "NPN"])
        self.sync()
        malformed = self.ranking([], "malformed", evaluated=NOW+timedelta(minutes=1))
        malformed.pop("opportunities")
        self.repo.saved["malformed"] = (PAPER_ACCOUNT, "ranking", (NOW+timedelta(minutes=1)).isoformat(), malformed)
        try:
            state = self.sync(NOW+timedelta(minutes=1))
        except ValueError:
            pass
        else:
            self.assertEqual(state["current_members"], ["NPN", "SASOL"])
        self.assertEqual(len(self.records("data-membership")), 1)

    def test_status_is_read_only_and_queue_waits_for_owner_login(self):
        self.ranking(["SASOL"])
        self.sync()
        original = deepcopy(self.repo.saved)
        self.repo.forbid_writes = True
        state = self.status()
        self.assertEqual(original, self.repo.saved)
        self.assertTrue(all(not row["automatic_download"] and not row["password_stored"] for row in state["requests"]))
        self.assertEqual(state["trading_weight"], 0)
        self.assertFalse(state["live_execution"])

    def test_monday_eight_sast_red_unless_actual_sources_imported(self):
        state = self.status()
        self.assertTrue(state["daily_reminder"]["due"])
        self.assertEqual(state["daily_reminder"]["state"], "IMPORT_REQUIRED")
        before = self.status(NOW-timedelta(seconds=1))
        self.assertFalse(before["daily_reminder"]["due"])

    def test_weekend_rolls_to_monday_without_inventing_exchange_holidays(self):
        saturday = datetime(2026, 10, 17, 8, tzinfo=timezone.utc)
        state = self.status(saturday)
        self.assertFalse(state["daily_reminder"]["due"])
        self.assertEqual(state["daily_reminder"]["next_window"], "2026-10-19T08:00:00+02:00")
        self.assertEqual(state["daily_reminder"]["exchange_holidays"], "NOT_ASSUMED_OPERATOR_CHECK")

    def test_dataset_refresh_does_not_refresh_actual_import_receipt(self):
        self.dataset(acquired=datetime(2026, 10, 15, 8, tzinfo=timezone.utc), session="2026-10-14", previous="2026-10-13")
        state = self.status()
        self.assertTrue(state["daily_reminder"]["due"])
        self.assertFalse(state["daily_reminder"]["all_required_current_today"])

    def test_actual_today_separate_complete_sources_and_benchmark_satisfy_routine(self):
        data = self.dataset()
        state = self.status()
        self.assertTrue(state["daily_reminder"]["all_required_current_today"])
        self.assertFalse(state["daily_reminder"]["due"])
        coverage = state["coverage"][0]
        self.assertIsNone(data["charts"]["SASOL"]["bars"][-1]["open"])
        self.assertTrue(coverage["daily_ready"])
        self.assertFalse(coverage["history_target_met"])
        self.assertFalse(coverage["historical_ai_admitted"])

    def test_invalid_raw_hash_or_future_capture_never_satisfies_routine(self):
        for field, value in (("source_sha256", "not-a-sha256"), ("acquired_at", (NOW+timedelta(seconds=1)).isoformat())):
            data = self.dataset()
            data["research_charts"]["SASOL"]["provenance"][field] = value
            self.store_dataset(data)
            self.assertFalse(self.status()["daily_reminder"]["all_required_current_today"])

    def test_missing_earlier_iress_open_or_estimated_bar_blocks_complete_source(self):
        for bad in ({"open": None}, {"estimated": True}, {"volume": None}):
            data = self.dataset()
            data["research_charts"]["SASOL"]["bars"][0].update(bad)
            self.store_dataset(data)
            self.assertFalse(self.status()["coverage"][0]["daily_ready"])

    def test_today_receipt_with_stale_bar_history_stays_red(self):
        self.dataset(session="2026-10-14", previous="2026-10-13")
        self.assertFalse(self.status()["daily_reminder"]["all_required_current_today"])

    def test_wrong_origin_identity_never_marks_complete_source(self):
        data = self.dataset()
        data["research_charts"]["SASOL"]["provenance"]["origin_symbol"] = "NPN.JSE"
        self.store_dataset(data)
        self.assertFalse(self.status()["coverage"][0]["daily_ready"])

    def test_all_three_completed_session_dates_must_align(self):
        for target in ("SASOL", "ETF_STX40"):
            data = self.dataset()
            data["charts"][target]["bars"] = [data["charts"][target]["bars"][0]]
            self.store_dataset(data)
            self.assertFalse(self.status()["coverage"][0]["daily_ready"])

    def test_prompt_has_exact_required_codes_and_preserves_source_and_local_boundaries(self):
        self.ranking(["SASOL", "NPN"])
        self.sync()
        prompt = self.status()["copyable_prompt"]
        self.assertIn("SASOL (SOL)", prompt)
        self.assertIn("NPN (NPN)", prompt)
        for phrase in ("SEPARATE", "Exclude the live row", "actual acquisition", "raw bytes/hash", "No Railway upload",
                       "No orders", "no password storage", "integer cents/whole volume", "3/4/5"):
            self.assertIn(phrase, prompt)

    def test_storage_arithmetic_exposes_snapshot_growth_and_bounds_catalog_reuse(self):
        estimate = requests.storage_estimate(None, slots=5, weekly_churn=5, retained_weeks=12)
        self.assertEqual(estimate["maximum_unique_registered_candidates"], 18)
        self.assertEqual(estimate["active_history_bytes"], 16*600*300)
        self.assertEqual(estimate["additional_candidate_history_bytes"], 13*2*600*300)
        self.assertEqual(estimate["full_daily_snapshot_bytes_per_252_sessions"], estimate["active_history_bytes"]*252)
        self.assertGreater(estimate["full_daily_snapshot_bytes_per_252_sessions"], estimate["incremental_price_bytes_per_252_sessions"])
        self.assertFalse(estimate["retention_applied"])
        self.assertFalse(estimate["automatic_deletion"])
        self.assertTrue(estimate["news_reports_raw_documents_and_database_backup_costs_not_included"])

    def test_storage_preflight_distinguishes_measured_dataset_from_planning(self):
        data = self.dataset()
        estimate = requests.storage_estimate(data)
        self.assertEqual(estimate["measured_bar_count"], 6)
        self.assertEqual(estimate["measured_series_count"], 3)
        self.assertEqual(estimate["measured_current_dataset_bytes"], len(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()))

    def test_storage_rejects_unbounded_or_noninteger_planning_inputs(self):
        for kwargs in ({"slots": True}, {"slots": 19}, {"weekly_churn": 10**100}, {"retained_weeks": 521}, {"weekly_churn": -1}):
            with self.assertRaises(ValueError):
                requests.storage_estimate(None, **kwargs)


if __name__ == "__main__":
    unittest.main()
