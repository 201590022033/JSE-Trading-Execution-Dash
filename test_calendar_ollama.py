"""Offline runner safety: no model requests, native configuration or external IO."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import research_calendar as calendar
from market_intelligence import calendar_expectations as expectations
from scripts import calendar_ollama as runner

NOW = datetime(2026, 10, 19, 8, tzinfo=timezone.utc)


class Owner:
    closed = False
    def __init__(self, *args): pass
    def __enter__(self): Owner.closed = False; return self
    def owns_listener(self): return True
    def __exit__(self, *args): Owner.closed = True


class Response:
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): pass
    def json(self): return self.payload
    def iter_content(self, maximum): yield json.dumps(self.payload).encode()
    def close(self): pass


class Session:
    def __init__(self): self.posts = []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def get(self, url, **kwargs):
        assert url == runner.HOST + "/api/tags"
        return Response({"models": [{"name": runner.MODEL, "digest": runner.MODEL_DIGEST}]})
    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return Response({"done": True, "response": '{"proposals": []}'})


class CalendarOllamaTests(unittest.TestCase):
    def setUp(self):
        memory_patch = patch.object(runner, "available_memory_bytes", return_value=8 * runner.GIB)
        memory_patch.start(); self.addCleanup(memory_patch.stop)
        idle_patch = patch.object(runner, "windows_idle_seconds", return_value=1)
        idle_patch.start(); self.addCleanup(idle_patch.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.db = self.folder / "test.db"
        self.repo = SQLiteRepository(self.db)
        self.addCleanup(lambda: self.repo.close())
        source = calendar.import_source(self.repo, {"source_url": "https://example.test/calendar", "title": "Sasol",
            "body": "Sasol Q1 metrics 22 October 2026", "captured_at": NOW.isoformat(), "provenance": "test capture"}, NOW)
        self.event = calendar.propose_event(self.repo, {"event_key": "sasol-q1", "title": "Sasol quarterly metrics",
            "instrument_ids": ["SASOL"], "source_receipt_id": source["record_id"], "source_quote": source["body"],
            "event_date": "2026-10-22", "timezone": "Africa/Johannesburg"}, NOW)
        calendar.confirm_event(self.repo, self.event["record_id"], "test operator", NOW)

    def execute(self, generator, idle=lambda: 601):
        with patch.object(runner, "utcnow", return_value=NOW + timedelta(seconds=1)):
            return runner.execute(self.repo, NOW, self.folder, "existing-ollama.exe", idle=idle, generator=generator)

    def test_active_pc_never_prepares_reserves_or_calls(self):
        def forbidden(*args, **kwargs): raise AssertionError("generation forbidden")
        result = self.execute(forbidden, idle=lambda: 1)
        self.assertEqual(result["state"], "WAITING_FOR_10_MINUTES_IDLE")
        self.assertEqual(runner.runner_status(self.repo, NOW)["total_reservations"], 0)

    def test_insufficient_memory_does_not_prepare_reserve_or_generate(self):
        def forbidden(*args, **kwargs): raise AssertionError("generation forbidden")
        result = runner.execute(self.repo, NOW, self.folder, "x", idle=lambda: 601,
            memory=lambda: 6 * runner.GIB, generator=forbidden)
        self.assertEqual(result["state"], "WAITING_FOR_MEMORY")
        self.assertEqual(runner.runner_status(self.repo, NOW)["total_reservations"], 0)

    def test_reserve_before_call_and_restart_never_repeats(self):
        calls = []
        def generate(packet, *args, **kwargs):
            saved = self.repo.paper_record(runner.attempt_id(self.event["event_key"], NOW))
            self.assertEqual(saved["input_sha256"], packet["input_sha256"])
            calls.append(packet)
            return (b'{"done":true,"response":"{\\"proposals\\":[]}"}', '{"proposals":[]}',
                    NOW + timedelta(seconds=1), NOW + timedelta(seconds=1))
        result = self.execute(generate)
        self.assertEqual(result["model_calls"], 1)
        self.assertTrue(result["domain_result_id"].startswith("calendar-expectation-run-"))
        self.assertEqual(result["proposal_ids"], [])
        self.repo.close(); self.repo = SQLiteRepository(self.db)
        self.assertEqual(self.execute(generate)["model_calls"], 0)
        self.assertEqual(len(calls), 1)
        status = runner.runner_status(self.repo, NOW + timedelta(seconds=2))
        self.assertEqual(status["completed_generation_calls"], 1)
        self.assertEqual(status["model_calls_on_read"], 0)

    def test_failure_consumes_day_budget_and_changed_input_cannot_reset(self):
        def failure(*args, **kwargs): raise TimeoutError()
        first = self.execute(failure)
        self.assertEqual(first["state"], "FAILED_NO_AUTOMATIC_RETRY")
        packet = expectations.prepare_input(self.repo, self.event["record_id"], NOW + timedelta(seconds=2))
        _, acquired = runner.reserve(self.repo, self.event["record_id"], packet, NOW + timedelta(seconds=2))
        self.assertFalse(acquired)
        self.assertEqual(self.execute(failure)["model_calls"], 0)

    def test_event_revision_does_not_reset_stable_event_day_budget(self):
        packet = expectations.prepare_input(self.repo, self.event["record_id"], NOW)
        runner.reserve(self.repo, self.event["record_id"], packet, NOW)
        revised = dict(packet); revised["event"] = dict(packet["event"], record_id="new-event-version")
        revised["input_sha256"] = "changed"
        _, acquired = runner.reserve(self.repo, "new-event-version", revised, NOW + timedelta(minutes=1))
        self.assertFalse(acquired)

    def test_crashed_reservation_and_missing_result_are_visible_not_retryable(self):
        packet = expectations.prepare_input(self.repo, self.event["record_id"], NOW)
        runner.reserve(self.repo, self.event["record_id"], packet, NOW)
        status = runner.runner_status(self.repo, NOW)
        self.assertEqual(status["unresolved_reservations"], 1)
        self.assertEqual(status["uncertain_generation_call_upper_bound"], 1)
        self.assertEqual(status["completed_generation_calls"], 0)
        def forbidden(*args, **kwargs): raise AssertionError("crash retry forbidden")
        self.assertEqual(self.execute(forbidden)["model_calls"], 0)

    def test_failed_domain_registration_retains_actual_raw_response_reference(self):
        raw = b'{"done":true,"response":"{\\"proposals\\":[]}"}'
        def generator(*args, **kwargs):
            return raw, '{"proposals":[]}', NOW + timedelta(seconds=1), NOW + timedelta(seconds=1)
        with patch.object(expectations, "register_response", side_effect=ValueError("input superseded")):
            result = self.execute(generator)
        self.assertEqual(result["state"], "FAILED_NO_AUTOMATIC_RETRY")
        saved = result["response_archive"]
        self.assertEqual((self.folder / saved["name"]).read_bytes(), raw)
        self.assertEqual(saved["sha256"], runner.sha256(raw).hexdigest())
        status = runner.runner_status(self.repo, NOW + timedelta(seconds=2))
        self.assertEqual(status["unresolved_reservations"], 0)
        self.assertEqual(status["uncertain_generation_call_upper_bound"], 1)
        self.assertEqual(self.execute(generator)["model_calls"], 0)

    def test_sast_day_boundary_not_utc_and_next_day_separate_budget(self):
        before = datetime(2026, 10, 19, 21, 59, tzinfo=timezone.utc)
        after = before + timedelta(minutes=2)
        self.assertNotEqual(runner.attempt_id("event", before), runner.attempt_id("event", after))

    def test_cancelled_user_input_records_no_automatic_retry(self):
        def interrupted(*args, **kwargs): raise InterruptedError()
        self.assertEqual(self.execute(interrupted)["state"], "CANCELLED_USER_RETURNED")
        self.assertEqual(self.execute(interrupted)["model_calls"], 0)

    def test_local_generation_exact_host_model_and_hard_cpu_bounds(self):
        session = Session()
        raw, text, started, completed = runner.generate({}, "source packet", {}, "existing.exe", self.folder,
            idle=lambda: 601, session_factory=lambda: session, owner_factory=Owner)
        self.assertEqual(text, '{"proposals": []}')
        self.assertLessEqual(started, completed)
        self.assertTrue(Owner.closed)
        self.assertEqual(len(session.posts), 1)
        url, call = session.posts[0]
        self.assertEqual(url, "http://127.0.0.1:11435/api/generate")
        self.assertFalse(call["allow_redirects"])
        self.assertEqual(call["json"]["options"], {"num_thread": 2, "num_gpu": 0,
            "num_ctx": 4096, "num_predict": 400, "temperature": 0})
        self.assertEqual(call["json"]["keep_alive"], 0)
        self.assertLessEqual(call["timeout"][1], 180)

    def test_wrong_model_digest_never_generates(self):
        session = Session()
        session.get = lambda *args, **kwargs: Response({"models": [{"name": runner.MODEL, "digest": "changed"}]})
        with self.assertRaisesRegex(ValueError, "digest"):
            runner.generate({}, "prompt", {}, "x", self.folder, idle=lambda: 601,
                session_factory=lambda: session, owner_factory=Owner)
        self.assertEqual(session.posts, [])
        self.assertTrue(Owner.closed)

    def test_explicit_foreground_idle_override_keeps_default_and_memory_checks(self):
        session=Session()
        with self.assertRaises(InterruptedError):
            runner.generate({},'prompt',{},'x',self.folder,idle=lambda:0,
                session_factory=lambda:session,owner_factory=Owner)
        self.assertEqual(session.posts,[])
        runner.generate({},'prompt',{},'x',self.folder,idle=lambda:0,required_idle_seconds=0,
            session_factory=lambda:session,owner_factory=Owner)
        self.assertEqual(len(session.posts),1)
        with self.assertRaises(runner.ResourcePressure):
            runner.generate({},'prompt',{},'x',self.folder,idle=lambda:0,required_idle_seconds=0,
                memory=lambda:runner.GIB,session_factory=lambda:session,owner_factory=Owner)

    def test_listener_ownership_failure_does_not_send_http(self):
        class WrongOwner(Owner):
            def owns_listener(self): raise RuntimeError("wrong PID")
        class ForbiddenSession(Session):
            def get(self, *args, **kwargs): raise AssertionError("unowned GET forbidden")
        with self.assertRaisesRegex(RuntimeError, "wrong PID"):
            runner.generate({}, "prompt", {}, "x", self.folder, idle=lambda: 601,
                session_factory=ForbiddenSession, owner_factory=WrongOwner)

    def test_active_return_during_generation_closes_owned_process_tree(self):
        started = threading.Event()
        finished = threading.Event()
        class BlockingSession(Session):
            def post(self, *args, **kwargs):
                started.set(); finished.wait(2)
                return Response({"done": True, "response": '{"proposals":[]}'})
        class ClosingOwner(Owner):
            def __exit__(self, *args): finished.set(); super().__exit__(*args)
        with self.assertRaises(InterruptedError):
            runner.generate({}, "prompt", {}, "x", self.folder,
                idle=lambda: 0 if started.is_set() else 601,
                session_factory=BlockingSession, owner_factory=ClosingOwner)
        self.assertTrue(Owner.closed)
        self.assertTrue(finished.wait(1))

    def test_incomplete_response_archived_but_never_accepted(self):
        session = Session()
        session.post = lambda *args, **kwargs: Response({"done": True, "done_reason": "length", "response": "partial"})
        with self.assertRaises(runner.ModelResponseError) as caught:
            runner.generate({}, "prompt", {}, "x", self.folder, idle=lambda: 601,
                session_factory=lambda: session, owner_factory=Owner)
        self.assertTrue((self.folder / caught.exception.archive["name"]).is_file())

    def test_memory_pressure_during_call_closes_owned_tree_and_consumes_budget(self):
        started, finished = threading.Event(), threading.Event()
        class BlockingSession(Session):
            def post(self, *args, **kwargs):
                started.set(); finished.wait(2)
                return Response({"done": True, "response": '{"proposals":[]}'})
        class ClosingOwner(Owner):
            def __exit__(self, *args): finished.set(); super().__exit__(*args)
        def generator(packet, prompt, schema, executable, folder, **kwargs):
            return runner.generate(packet, prompt, schema, executable, folder, idle=lambda: 601,
                memory=lambda: runner.GIB if started.is_set() else 8 * runner.GIB,
                session_factory=BlockingSession, owner_factory=ClosingOwner)
        result = self.execute(generator)
        self.assertEqual(result["state"], "RESOURCE_PRESSURE")
        self.assertTrue(Owner.closed)
        self.assertEqual(self.execute(generator)["model_calls"], 0)

    def test_status_and_dry_read_do_not_create_attempts_or_inputs(self):
        before = self.repo._job_sql("SELECT COUNT(*) FROM paper_records", rows=True)[0][0]
        self.assertEqual(runner.runner_status(self.repo, NOW)["due_events"], 1)
        self.assertEqual(before, self.repo._job_sql("SELECT COUNT(*) FROM paper_records", rows=True)[0][0])

    def test_status_reports_actual_resource_wait_without_model_or_reservation(self):
        status = runner.runner_status(self.repo, NOW, idle=lambda: 650, memory=lambda: 4 * runner.GIB)
        self.assertEqual(status["readiness_state"], "WAITING_FOR_MEMORY")
        self.assertEqual(status["available_physical_ram_gib"], 4)
        self.assertFalse(status["resources_ready"])
        self.assertEqual(status["total_reservations"], 0)
        self.assertEqual(runner.runner_status(self.repo, NOW, idle=lambda: 1,
            memory=lambda: 8 * runner.GIB)["readiness_state"], "WAITING_FOR_10_MINUTES_IDLE")
        self.assertTrue(runner.runner_status(self.repo, NOW, idle=lambda: 650,
            memory=lambda: 8 * runner.GIB)["resources_ready"])


if __name__ == "__main__":
    unittest.main()
