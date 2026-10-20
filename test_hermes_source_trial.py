"""Actual-packet trial contracts with mocked inference, never real labels/trades."""
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest

import test_calendar_expectations as fixture
from scripts.hermes_source_trial import execute_trial
from scripts import calendar_ollama as runner
from scripts import calibrate_calendar_model as calibration


class SourceTrialTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.CalendarExpectationTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.capture()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        path = self.folder/"qwen-calibration-v1"
        path.mkdir()
        (path/"result.json").write_text(json.dumps({"state": "CALIBRATION_FIXTURE_PASSED",
            "exact_fixture_passed": True, "telemetry_errors": [],
            "profile_sha256": calibration._digest(calibration.PROFILE), "profile": calibration.PROFILE}))
        self.original = (runner.MODEL, runner.MODEL_DIGEST, runner.MIN_START_MEMORY)

    def run_trial(self, generator, **kwargs):
        return execute_trial(self.f.repo, fixture.NOW, self.folder, "fixture-not-executed",
            idle=kwargs.get("idle", lambda: 601), memory=kwargs.get("memory", lambda: 4*runner.GIB), generator=generator)

    def test_current_source_abstention_validates_and_preserves_production_profile(self):
        def generate(packet, prompt, schema, *args, **kwargs):
            self.assertEqual(runner.MODEL, calibration.MODEL)
            self.assertEqual(runner.MIN_START_MEMORY, 7*runner.GIB//2)
            self.assertIn("Sasol", prompt)
            self.assertNotIn("SYNTHETIC FIXTURE", prompt)
            proposal = self.f.proposal(packet, direction="ABSTAIN")
            content = json.dumps({"proposals": [proposal]})
            return json.dumps({"done": True, "response": content}).encode(), content, fixture.NOW, fixture.NOW+timedelta(seconds=1)
        result = self.run_trial(generate)
        self.assertEqual(result["state"], "MODEL_DRAFT_RECORDED_REQUIRES_REVIEW")
        self.assertEqual(result["model_calls"], 1)
        self.assertFalse(result["production_profile_changed"])
        self.assertEqual((runner.MODEL, runner.MODEL_DIGEST, runner.MIN_START_MEMORY), self.original)
        retry = self.run_trial(lambda *a, **k: self.fail("duplicate generation"))
        self.assertEqual(retry["state"], "NO_UNRESERVED_DUE_SASOL_EVENT")

    def test_idle_memory_and_failure_controls_remain_in_force(self):
        forbidden = lambda *a, **k: self.fail("generated while gated")
        self.assertEqual(self.run_trial(forbidden, idle=lambda: 0)["state"], "WAITING_FOR_10_MINUTES_IDLE")
        self.assertEqual(self.run_trial(forbidden, memory=lambda: 3*runner.GIB)["state"], "WAITING_FOR_MEMORY")
        def failed(*args, **kwargs): raise RuntimeError("synthetic provider failure")
        self.assertEqual(self.run_trial(failed)["state"], "FAILED_NO_AUTOMATIC_RETRY")
        self.assertEqual(self.run_trial(forbidden)["state"], "NO_UNRESERVED_DUE_SASOL_EVENT")
        self.assertEqual((runner.MODEL, runner.MODEL_DIGEST, runner.MIN_START_MEMORY), self.original)

    def test_wrong_calibration_cannot_authorize_trial(self):
        path = self.folder/"qwen-calibration-v1"/"result.json"
        path.write_text(json.dumps({"state": "NOT_RUN"}))
        with self.assertRaises(ValueError):
            self.run_trial(lambda *a, **k: self.fail("model"))

    def test_stale_full_calibration_profile_cannot_authorize_trial(self):
        path = self.folder/"qwen-calibration-v1"/"result.json"
        data = json.loads(path.read_text())
        data["profile_sha256"] = "0"*64
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.run_trial(lambda *a, **k: self.fail("model"))


if __name__ == "__main__":
    unittest.main()
