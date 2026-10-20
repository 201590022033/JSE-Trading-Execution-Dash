"""Audited native IRESS transforms, whole-source routing and immutable lineage."""
from copy import deepcopy
import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest

from persistence.sqlite_repository import SQLiteRepository
from application.opportunities import source_transforms as transforms
from application.opportunities.source_resolution import parse_iress_export, attach_iress_research
from application.opportunities.ost_data import catalog, POLICY, SCHEMA
from application.opportunities.swing_research import validate_dataset, accept_dataset, latest_dataset, UploadedFetcher

NOW = datetime(2026, 10, 20, 8, tzinfo=timezone.utc)


class SourceTransformTests(unittest.TestCase):
    def raw(self, key="SASOL", *, conflict=False, fraction=False, duplicates=True, percent="999"):
        scale = 10 if key == "NPN" else 1
        values = [10000*scale, 10500*scale, 9500*scale, 10200*scale, 1200]
        duplicate = list(values)
        if conflict:
            duplicate[3] += 1
        if fraction:
            duplicate[4] = "1200.5"
        rows = [["2026-10-15T22:00:00.000Z", *values[:4], "1", "2", values[4]]]
        if duplicates:
            rows.append(["2026-10-15T22:00:00.000Z", *duplicate[:4], percent, "-23", duplicate[4]])
        rows.extend([["2026-10-18T22:00:00.000Z", 10200*scale, 10800*scale, 10000*scale, 10700*scale, "3", "4", 1400],
                     ["2026-10-19T22:00:00.000Z", 10700*scale, 10900*scale, 10600*scale, 10800*scale, "4", "5", 20]])
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["Date", "Open", "High", "Low", "Close", "% Change", "% Change vs Average", "Volume"])
        writer.writerows(rows)
        return output.getvalue().encode()

    def primary(self, keys=("SASOL", "NPN"), now=NOW):
        charts = {}
        for key in (*keys, "ETF_STX40"):
            route = catalog()[key]
            charts[key] = {"symbol": route["symbol"], "currency": "ZAR", "interval": "1d", "bars": [
                {"timestamp": "2026-10-16", "open": None, "high": 105.0, "low": 95.0, "close": 102.0, "volume": 999},
                {"timestamp": "2026-10-19", "open": None, "high": 108.0, "low": 100.0, "close": 107.0, "volume": 999}],
                "provenance": {"provider": "OST", "origin_symbol": route["ost_code"], "purpose": "JSE_DAILY_RESEARCH",
                    "source_sha256": "a"*64, "acquired_at": now.isoformat(), "price_basis": "UNVERIFIED",
                    "volume_basis": "UNVERIFIED", "historical_availability": "UNVERIFIED"}}
        return {"schema": SCHEMA, "source_policy": POLICY, "observed_at": now.isoformat(), "charts": charts}

    def install(self, folder, key="SASOL", *, now=NOW, raw=None):
        return transforms.install_derived_iress(raw or self.raw(key), key, now.isoformat(), now, folder)

    def test_default_native_parser_still_rejects_duplicate_dates(self):
        with self.assertRaises(ValueError):
            parse_iress_export(self.raw(), "SASOL", "SOL.JSE", NOW.isoformat(), NOW)

    def test_explicit_transform_only_removes_equal_ohlcv_duplicate_and_derived_percent_columns(self):
        native = self.raw()
        derived, receipt = transforms.derive_iress_export(native, "SASOL", NOW.isoformat(), NOW)
        self.assertEqual(receipt["original_source_sha256"], sha256(native).hexdigest())
        self.assertEqual(receipt["derived_source_sha256"], sha256(derived).hexdigest())
        self.assertEqual((receipt["original_rows"], receipt["derived_rows"]), (4, 3))
        self.assertEqual(len(receipt["duplicates"]), 1)
        duplicate = receipt["duplicates"][0]
        self.assertEqual((duplicate["kept_csv_line"], duplicate["removed_csv_line"]), (2, 3))
        self.assertNotEqual(duplicate["derived_fields"]["% Change"]["kept"], duplicate["derived_fields"]["% Change"]["removed"])
        parsed = list(csv.DictReader(derived.decode().splitlines()))
        self.assertNotIn("% Change", parsed[0])
        self.assertEqual(parsed[0]["Open"], "10000")
        chart = parse_iress_export(derived, "SASOL", "SOL.JSE", NOW.isoformat(), NOW)
        self.assertEqual(len(chart["bars"]), 2)  # Live20Oct never admitted later by accident.
        self.assertEqual(chart["bars"][-1]["timestamp"], "2026-10-19")
        self.assertEqual(chart["bars"][-1]["open"], 102)

    def test_conflicting_ohlcv_fractional_units_and_unneeded_transform_rejected(self):
        for raw in (self.raw(conflict=True), self.raw(fraction=True), self.raw(duplicates=False)):
            with self.assertRaises(ValueError):
                transforms.derive_iress_export(raw, "SASOL", NOW.isoformat(), NOW)

    def test_truncated_native_row_is_an_explicit_validation_failure(self):
        with self.assertRaises(ValueError):
            transforms.derive_iress_export(self.raw()+b"truncated\n", "SASOL", NOW.isoformat(), NOW)

    def test_two_cash_sources_roundtrip_to_sql_and_numerical_fetch_without_mixing_ost_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            first, second = self.install(folder), self.install(folder, "NPN")
            primary = self.primary()
            before = deepcopy(primary)
            packet = attach_iress_research(primary, NOW, folder)
            self.assertEqual(primary, before)
            self.assertEqual(set(packet["research_charts"]), {"SASOL", "NPN"})
            self.assertEqual(set(packet["source_transform_receipts"]), {"SASOL", "NPN"})
            normalized = validate_dataset(packet, NOW)
            self.assertEqual(normalized["source_transform_receipts"]["NPN"], second["transform"])
            repo = SQLiteRepository(":memory:")
            try:
                accept_dataset(repo, normalized, NOW)
                self.assertEqual(latest_dataset(repo)["source_transform_receipts"]["SASOL"], first["transform"])
                fetcher = UploadedFetcher(repo, clock=lambda: NOW)
                for symbol, expected in (("SOL.JO", 102), ("NPN.JO", 1020)):
                    canonical = fetcher.get_chart(symbol, "1y")
                    research = fetcher.get_research_chart(symbol, NOW)
                    self.assertIsNone(canonical["bars"][-1]["open"])
                    self.assertEqual(canonical["bars"][-1]["volume"], 999)
                    self.assertEqual(research["bars"][-1]["open"], expected)
                    self.assertEqual(research["bars"][-1]["volume"], 1400)
                    self.assertEqual(research["provenance"]["acquired_at"], NOW.isoformat())
                    self.assertFalse(research["historical_evaluation_allowed"])
            finally:
                repo.close()

    def test_native_archive_tamper_quarantines_only_bad_chart(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            first = self.install(folder)
            self.install(folder, "NPN")
            native = folder/"alternative-exports"/("SASOL-IRESS-native-"+first["transform"]["original_source_sha256"]+".csv")
            native.write_bytes(native.read_bytes()+b"tamper")
            packet = attach_iress_research(self.primary(), NOW, folder)
            self.assertNotIn("SASOL", packet.get("research_charts", {}))
            self.assertIn("NPN", packet["research_charts"])
            self.assertIsNone(packet["charts"]["SASOL"]["bars"][-1]["open"])

    def test_derived_canonical_archive_tamper_cannot_feed_research(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            installed = self.install(folder)
            path = folder/"alternative-exports"/("SASOL-IRESS-"+installed["chart"]["source_sha256"]+".csv")
            path.write_bytes(path.read_bytes().replace(b"10000", b"10001", 1))
            packet = attach_iress_research(self.primary(), NOW, folder)
            self.assertNotIn("SASOL", packet.get("research_charts", {}))

    def test_missing_transform_manifest_never_downgrades_derived_data_to_native(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.install(folder)
            (folder/"source-transforms.json").unlink()
            packet = attach_iress_research(self.primary(), NOW, folder)
            self.assertNotIn("SASOL", packet.get("research_charts", {}))

    def test_transform_receipt_tamper_and_acquisition_edit_rejected_at_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.install(folder)
            packet = attach_iress_research(self.primary(), NOW, folder)
            for key, value in (("original_source_sha256", "0"*64), ("acquired_at", (NOW-timedelta(hours=1)).isoformat())):
                altered = deepcopy(packet)
                altered["source_transform_receipts"]["SASOL"][key] = value
                with self.assertRaises(ValueError):
                    validate_dataset(altered, NOW)

    def test_upstream_estimate_markers_cannot_be_erased_by_normalization(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.install(folder)
            packet = attach_iress_research(self.primary(), NOW, folder)
            for marker in ("estimated", "is_estimated", "synthetic"):
                altered = deepcopy(packet)
                altered["research_charts"]["SASOL"]["bars"][0][marker] = True
                with self.assertRaises(ValueError):
                    validate_dataset(altered, NOW)

    def test_percent_only_native_recapture_preserves_active_receipt_without_rejuvenation(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            first = self.install(folder)
            later = NOW+timedelta(hours=1)
            second = self.install(folder, now=later, raw=self.raw(percent="777"))
            self.assertEqual(first["transform"], second["transform"])
            self.assertEqual(second["state"], "DERIVED_CONTENT_REUSED_NO_RECEIPT_REFRESH")
            self.assertNotEqual(first["transform"]["original_source_sha256"], second["acquisition_attempt"]["original_source_sha256"])
            self.assertEqual(first["transform"]["derived_source_sha256"], second["transform"]["derived_source_sha256"])
            self.assertEqual(second["chart"]["acquired_at"], NOW.isoformat())
            packet = attach_iress_research(self.primary(now=later), later, folder)
            self.assertIn("SASOL", packet.get("research_charts", {}))
            self.assertEqual(packet["source_transform_receipts"]["SASOL"]["acquired_at"], NOW.isoformat())
            archived_attempt = folder/"transform-receipts"/(second["acquisition_attempt"]["receipt_sha256"]+".json")
            self.assertEqual(json.loads(archived_attempt.read_text())["acquired_at"], later.isoformat())
            native = folder/"alternative-exports"/("SASOL-IRESS-native-"+first["transform"]["original_source_sha256"]+".csv")
            self.assertEqual(sha256(native.read_bytes()).hexdigest(), first["transform"]["original_source_sha256"])


if __name__ == "__main__":
    unittest.main()
