"""Offline one-shot calibration contracts; no inference or database writes."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from scripts import calibrate_calendar_model as calibration
from scripts import calendar_ollama as runner

NOW = datetime(2026, 10, 20, 8, tzinfo=timezone.utc)


class FakeOwner:
    closed = False
    def __init__(self, *args): pass
    def __enter__(self): FakeOwner.closed = False; return self
    def __exit__(self, *args): FakeOwner.closed = True


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)/"calibration"
        self.exe = Path(self.tmp.name)/"test-only.exe"
        self.exe.write_bytes(b"fixture never executed")
        self.production = (runner.MODEL, runner.MODEL_DIGEST, runner.MIN_START_MEMORY, runner.MIN_RUNNING_MEMORY)

    def run_fixture(self, generator, **kwargs):
        return calibration.run(self.folder, self.exe, idle=kwargs.pop("idle", lambda: 601),
            memory=kwargs.pop("memory", lambda: 4*runner.GIB), generator=generator,
            owner_factory=FakeOwner, sample=kwargs.pop("sample", lambda owner: 512*1024**2),
            now=lambda: NOW, **kwargs)

    def successful(self, packet, prompt, schema, executable, folder, **kwargs):
        self.assertEqual(runner.MODEL, calibration.MODEL)
        self.assertEqual(runner.MIN_START_MEMORY, 3*runner.GIB)
        self.assertEqual(schema, calibration.SCHEMA)
        self.assertIn("SYNTHETIC FIXTURE", prompt)
        self.assertTrue((folder/"reservation.json").exists())
        with kwargs["owner_factory"](executable, folder):
            kwargs["memory"]()
        content = json.dumps(calibration.EXPECTED)
        return json.dumps({"done": True, "response": content}).encode(), content, NOW, NOW+timedelta(seconds=1)

    def assert_production_unchanged(self):
        self.assertEqual((runner.MODEL, runner.MODEL_DIGEST, runner.MIN_START_MEMORY, runner.MIN_RUNNING_MEMORY), self.production)

    def test_active_or_insufficient_memory_consumes_no_attempt(self):
        def forbidden(*args, **kwargs): raise AssertionError("inference")
        result = self.run_fixture(forbidden, idle=lambda: 599)
        self.assertEqual(result["state"], "WAITING_FOR_10_MINUTES_IDLE")
        result = self.run_fixture(forbidden, memory=lambda: 2*runner.GIB)
        self.assertEqual(result["state"], "WAITING_FOR_CALIBRATION_MEMORY")
        self.assertFalse(self.folder.exists())
        self.assert_production_unchanged()

    def test_exact_fixture_timestamps_telemetry_and_original_profile_preserved(self):
        result = self.run_fixture(self.successful)
        self.assertEqual(result["state"], "CALIBRATION_FIXTURE_PASSED")
        self.assertEqual(result["generation_calls"], 1)
        self.assertEqual(result["request_started_at"], NOW.isoformat())
        self.assertEqual(result["request_completed_at"], (NOW+timedelta(seconds=1)).isoformat())
        self.assertEqual(result["minimum_observed_free_ram_bytes"], 4*runner.GIB)
        self.assertEqual(result["peak_sampled_owned_working_set_bytes"], 512*1024**2)
        self.assertTrue((self.folder/result["raw_response"]["name"]).is_file())
        self.assertFalse(result["market_database_written"])
        self.assertFalse(result["automatic_promotion"])
        self.assertEqual(result["training_labels_created"], 0)
        self.assertTrue(FakeOwner.closed)
        self.assert_production_unchanged()

    def test_repeat_or_restart_never_generates_again(self):
        first = self.run_fixture(self.successful)
        def forbidden(*args, **kwargs): raise AssertionError("duplicate")
        self.assertEqual(first, self.run_fixture(forbidden))
        self.assertEqual(first, calibration.status(self.folder))

    def test_failure_is_final_and_profile_restores(self):
        def fail(*args, **kwargs): raise InterruptedError("user returned")
        result = self.run_fixture(fail)
        self.assertEqual(result["state"], "CALIBRATION_FAILED_NO_AUTOMATIC_RETRY")
        self.assertEqual(result["generation_calls_upper_bound"], 1)
        def forbidden(*args, **kwargs): raise AssertionError("retry")
        self.assertEqual(result, self.run_fixture(forbidden))
        self.assert_production_unchanged()

    def test_crashed_reservation_cannot_retry(self):
        self.folder.mkdir()
        (self.folder/"reservation.json").write_text(json.dumps({"profile_sha256": calibration._digest(calibration.PROFILE)}))
        def forbidden(*args, **kwargs): raise AssertionError("retry")
        result = self.run_fixture(forbidden)
        self.assertEqual(result["state"], "UNRESOLVED_CALIBRATION_NO_AUTOMATIC_RETRY")
        self.assertEqual(result["generation_calls_upper_bound"], 1)

    def test_changed_profile_receipt_fails_closed(self):
        self.folder.mkdir()
        (self.folder/"result.json").write_text('{"profile_sha256":"other"}')
        with self.assertRaises(ValueError):
            calibration.status(self.folder)

    def test_oracle_rejects_inexact_quote_extra_fields_or_duplicate_json(self):
        self.assertEqual(calibration.PROFILE["prompt_and_schema_characters"], 12000)
        self.assertGreater(len(calibration.PROMPT), 11000)
        self.assertIn(calibration.QUOTE, calibration.PROMPT[-200:])
        self.assertTrue(calibration.fixture_passed(json.dumps(calibration.EXPECTED)))
        for value in ({**calibration.EXPECTED, "quote": "invented"},
                      {**calibration.EXPECTED, "decision": "UP"}, {**calibration.EXPECTED, "extra": True}):
            self.assertFalse(calibration.fixture_passed(json.dumps(value)))
        self.assertFalse(calibration.fixture_passed('{"decision":"UP","decision":"ABSTAIN","source_id":"calibration-fixture","quote":'+json.dumps(calibration.QUOTE)+'}'))

    def test_telemetry_failure_closes_owned_job_and_does_not_certify_quality(self):
        def unavailable(owner): raise RuntimeError("telemetry unavailable")
        result = self.run_fixture(self.successful, sample=unavailable)
        self.assertEqual(result["state"], "CALIBRATION_FAILED_NO_AUTOMATIC_RETRY")
        self.assertTrue(FakeOwner.closed)
        self.assert_production_unchanged()


if __name__ == "__main__":
    unittest.main()
