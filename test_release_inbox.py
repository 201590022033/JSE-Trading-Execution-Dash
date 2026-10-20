"""X2 synthetic package, durable atomicity and inactive-boundary acceptance."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "packages/jse_intelligence_core/src"))
from application.release_inbox import ReleaseInbox, StorageError, load_profiles
from application.release_inbox import protocol
from jse_intelligence_core import score_news

FIXTURES = ROOT / "tests/fixtures/radar_inbox"
EXPECTED = json.loads((FIXTURES / "expected.json").read_text())


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def hashed(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def identity(value):
    return hashed(encoded(value).rstrip(b"\n"))


class ReleaseInboxTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.package = self.root / "package"
        shutil.copytree(FIXTURES / "complete", self.package)
        self.profiles = load_profiles(FIXTURES / "profiles.json")
        self.inbox = ReleaseInbox(self.root / "store", self.profiles, allow_test_profiles=True)

    def load(self, name):
        return json.loads((self.package / name).read_text())

    def save(self, name, value):
        (self.package / name).write_bytes(encoded(value))

    def seal(self, envelope=None):
        envelope = envelope or self.load("envelope.json")
        self.save("envelope.json", envelope)
        self.save("COMPLETE.json", dict(schema_version="radar-inbox-complete/1",
                                        envelope_hash=hashed((self.package / "envelope.json").read_bytes())))

    def change_manifest(self, change):
        manifest = self.load("manifest.json")
        change(manifest)
        self.save("manifest.json", manifest)
        envelope = self.load("envelope.json")
        envelope["manifest"]["byte_hash"] = hashed((self.package / "manifest.json").read_bytes())
        envelope["expected_manifest_id"] = identity(manifest)
        self.seal(envelope)

    def change_evidence(self, change):
        value = self.load("artifacts/evidence.json")
        change(value)
        self.save("artifacts/evidence.json", value)
        envelope = self.load("envelope.json")
        entry = next(d for d in envelope["artifacts"] if d["reference_id"] == "synthetic:evidence-1")
        entry.update(byte_hash=hashed((self.package / entry["path"]).read_bytes()), canonical_id=identity(value))
        self.seal(envelope)
        self.change_manifest(lambda m: m["evidence_references"][0].update(content_hash=identity(value)))

    def counts(self):
        with closing(sqlite3.connect(self.inbox.path)) as con:
            return tuple(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                         for t in ("packages", "files", "acknowledgements"))

    def reject(self, reason):
        ack = self.inbox.process(self.package)
        self.assertEqual((ack["outcome"], ack["reason_code"], ack["state"]), ("REJECTED", reason, None))
        self.assertEqual(self.inbox.get_ack(ack["ack_id"]), ack)
        self.assertEqual(self.counts()[:2], (0, 0))
        return ack

    def test_fixed_package_persists_bytes_identity_and_actual_ack_then_reopens(self):
        before = datetime.now(timezone.utc)
        ack = self.inbox.process(self.package)
        after = datetime.now(timezone.utc)
        for key in ("package_id", "manifest_id", "release_id", "release_version", "profile_id", "test_only"):
            self.assertEqual(ack[key], EXPECTED[key])
        self.assertEqual([ack[k] for k in ("outcome", "reason_code", "state")], EXPECTED["outcomes"]["imported"])
        self.assertEqual(ack["schema_version"], "radar-inbox-ack/1")
        self.assertEqual(set(ack), {"schema_version", "ack_id", "received_at", "package_id", "manifest_id",
                                    "release_id", "release_version", "profile_id", "test_only", "outcome", "reason_code", "state"})
        self.assertEqual(uuid.UUID(ack["ack_id"]).version, 4)
        self.assertLessEqual(before, datetime.fromisoformat(ack["received_at"].replace("Z", "+00:00")))
        self.assertLessEqual(datetime.fromisoformat(ack["received_at"].replace("Z", "+00:00")), after)
        reopened = ReleaseInbox(self.root / "store", self.profiles, allow_test_profiles=True)
        self.assertEqual(reopened.get_ack(ack["ack_id"]), ack)
        record = reopened.get_release(ack["package_id"])
        self.assertEqual(record["state"], "INACTIVE")
        self.assertTrue(record["profile"]["test_only"])
        for name, expected in EXPECTED["files"].items():
            body = reopened.read_file(ack["package_id"], name)
            self.assertEqual(hashed(body), expected)
            self.assertEqual(body, (self.package / name).read_bytes())
        again = reopened.process(self.package)
        self.assertEqual([again[k] for k in ("outcome", "reason_code", "state")], EXPECTED["outcomes"]["repeat"])
        self.assertNotEqual(again["ack_id"], ack["ack_id"])
        self.assertEqual(self.counts(), (1, 11, 2))

    def test_missing_marker_is_durable_pending_not_rejection(self):
        (self.package / "COMPLETE.json").unlink()
        ack = self.inbox.process(self.package)
        self.assertEqual([ack[k] for k in ("outcome", "reason_code", "state")], EXPECTED["outcomes"]["pending"])
        self.assertIsNone(ack["package_id"])
        self.assertEqual(self.inbox.get_ack(ack["ack_id"]), ack)
        self.assertEqual(self.counts(), (0, 0, 1))

    def test_repeat_retains_original_test_label_after_support_config_changes(self):
        first = self.inbox.process(self.package)
        profile = self.profiles[0].to_dict()
        profile["test_only"] = False
        service = ReleaseInbox(self.root / "store", (protocol.SupportedProfile.from_dict(profile),))
        again = service.process(self.package)
        self.assertEqual(again["outcome"], "ALREADY_IMPORTED")
        self.assertTrue(again["test_only"])
        self.assertTrue(service.get_release(first["package_id"])["profile"]["test_only"])

    def test_missing_referenced_file_and_modified_bytes(self):
        path = self.package / "artifacts/document.json"
        raw = path.read_bytes()
        path.unlink()
        self.reject("MISSING_FILE")
        path.write_bytes(raw + b" ")
        self.reject("BAD_DIGEST")

    def test_duplicate_keys_nonfinite_and_unknown_envelope_version(self):
        raw = (self.package / "envelope.json").read_bytes()
        duplicate = raw.replace(b'{', b'{"profile_id":"duplicate",', 1)
        (self.package / "envelope.json").write_bytes(duplicate)
        self.save("COMPLETE.json", dict(schema_version="radar-inbox-complete/1", envelope_hash=hashed(duplicate)))
        self.reject("INVALID_JSON")
        (self.package / "envelope.json").write_bytes(raw)
        env = self.load("envelope.json")
        env["schema_version"] = "radar-inbox-envelope/2"
        self.seal(env)
        self.reject("UNSUPPORTED_VERSION")
        for payload in (b'{"x":NaN}', b'{"x":1e999}', b'{"x":1,"x":2}', b'\xff'):
            with self.assertRaises(protocol.Rejection):
                protocol.parse_json(payload)

    def test_unknown_manifest_version_and_fields_reject(self):
        original = self.load("manifest.json")
        self.change_manifest(lambda m: m.update(schema_version="radar-release-manifest/2"))
        self.reject("UNSUPPORTED_VERSION")
        self.change_manifest(lambda m: (m.update(original), m.update(activate=True)))
        self.reject("INVALID_CONTRACT")

    def test_traversal_absolute_stream_device_and_case_collisions(self):
        env = self.load("envelope.json")
        for name in ("../escape.json", "/absolute.json", "C:/escape.json", "a\\file.json", "file.json:stream", "CON.json", "a/../file.json"):
            with self.subTest(path=name):
                changed = copy.deepcopy(env)
                changed["manifest"]["path"] = name
                self.seal(changed)
                self.reject("UNSAFE_PATH")
        changed = copy.deepcopy(env)
        changed["artifacts"][0]["path"] = "MANIFEST.json"
        self.seal(changed)
        self.reject("UNSAFE_PATH")

    def test_hardlink_escape_rejects_without_reading_target(self):
        path = self.package / "artifacts/document.json"
        outside = self.root / "outside.json"
        path.rename(outside)
        os.link(outside, path)
        self.reject("UNSAFE_PATH")
        self.assertTrue(outside.exists())

    def test_directory_link_escape_rejects(self):
        directory = self.package / "artifacts"
        outside = self.root / "outside"
        directory.rename(outside)
        if os.name == "nt":
            result = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(directory), str(outside)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            directory.symlink_to(outside, target_is_directory=True)
        self.addCleanup(lambda: os.rmdir(directory) if os.name == "nt" else directory.unlink())
        self.reject("UNSAFE_PATH")
        self.assertTrue((outside / "document.json").exists())

    def test_profiles_are_explicit_test_only_and_exact_scope(self):
        unknown = ReleaseInbox(self.root / "unknown")
        self.assertEqual(unknown.process(self.package)["reason_code"], "UNSUPPORTED_PROFILE")
        no_test = ReleaseInbox(self.root / "no-test", self.profiles)
        self.assertEqual(no_test.process(self.package)["reason_code"], "TEST_PROFILE_DISABLED")
        self.change_manifest(lambda m: m["scope"]["universe"].update(as_of="2026-01-02"))
        self.reject("UNSUPPORTED_SCOPE")

    def test_scope_product_context_role_and_compatibility_reject(self):
        original = self.load("manifest.json")
        variants = [(dict(vehicles=[dict(instrument_id="context:USDZAR", product_type="currency_product")]), "INVALID_CONTRACT"),
                    (dict(vehicles=[dict(instrument_id="JSE:SYNTH_BANK", product_type="ssf")]), "INVALID_CONTRACT"),
                    (dict(role="policy"), "UNSUPPORTED_CAPABILITY"),
                    (dict(horizons=["next_5m"]), "UNSUPPORTED_CAPABILITY"),
                    (dict(model_format_version="pickle-v1"), "UNSUPPORTED_CAPABILITY"),
                    (dict(scorer_version="other-v1"), "UNSUPPORTED_CAPABILITY")]
        for changes, reason in variants:
            self.change_manifest(lambda m: (m.clear(), m.update(copy.deepcopy(original)), m.update(changes)))
            self.reject(reason)

    def test_references_hash_conflicts_and_unsupported_executable_format(self):
        self.change_manifest(lambda m: m["content_references"][0].update(content_hash="sha256:" + "0" * 64))
        self.reject("REFERENCE_MISMATCH")
        env = self.load("envelope.json")
        env["artifacts"][0]["format"] = "pickle/1"
        self.seal(env)
        self.reject("UNSUPPORTED_FORMAT")

    def test_evidence_naive_clock_future_receipt_and_identity_reject(self):
        original = self.load("artifacts/evidence.json")
        for changes, reason in ((dict(received_at="2026-01-02T09:02:00"), "INVALID_CONTRACT"),
                                (dict(received_at="2099-01-01T00:00:00Z"), "EVIDENCE_LINK"),
                                (dict(evidence_id="synthetic:wrong"), "REFERENCE_MISMATCH")):
            self.change_evidence(lambda e: (e.clear(), e.update(copy.deepcopy(original)), e.update(changes)))
            self.reject(reason)

    def make_correction(self, mismatch=False):
        old = self.load("artifacts/evidence.json")
        old["evidence_id"] = "synthetic:original"
        if mismatch:
            old["event_id"] = "synthetic:other-event"
        self.save("artifacts/original.json", old)
        env = self.load("envelope.json")
        env["artifacts"].append(dict(reference_id=old["evidence_id"], path="artifacts/original.json",
                                     format="evidence-reference/1", byte_hash=hashed(encoded(old)), canonical_id=identity(old)))
        self.seal(env)
        self.change_evidence(lambda e: e.update(revision_kind="correction", original_reference=dict(
            reference_id=old["evidence_id"], content_hash=identity(old))))

    def test_complete_correction_chain_validates_and_inconsistent_event_rejects(self):
        self.make_correction(mismatch=True)
        self.reject("EVIDENCE_LINK")
        # Same synthetic chain with matching event identity is a valid inactive package.
        self.change_evidence(lambda e: e.update(event_id="synthetic:other-event"))
        self.assertEqual(self.inbox.process(self.package)["outcome"], "IMPORTED_INACTIVE")

    def test_missing_original_and_wrong_document_digest_reject(self):
        self.change_evidence(lambda e: e.update(revision_kind="correction", original_reference=dict(
            reference_id="synthetic:absent", content_hash="sha256:" + "0" * 64)))
        self.reject("REFERENCE_MISMATCH")
        self.change_evidence(lambda e: e.update(revision_kind="original", original_reference=None, content_hash="sha256:" + "0" * 64))
        self.reject("REFERENCE_MISMATCH")

    def test_limits_and_undeclared_file(self):
        (self.package / "extra.json").write_text('{}')
        self.reject("UNDECLARED_FILE")
        (self.package / "extra.json").unlink()
        (self.package / "artifacts/document.json").write_bytes(b' ' * (protocol.MAX_FILE_BYTES + 1))
        self.reject("LIMIT_EXCEEDED")
        with self.assertRaises(protocol.Rejection):
            protocol.parse_json(encoded({"x": [[[[[[[[[[[[[[[[[[0]]]]]]]]]]]]]]]]]]}))

    def test_source_completion_change_cannot_commit(self):
        original = protocol.read_file
        seen = 0
        def changing(root, name):
            nonlocal seen
            raw = original(root, name)
            if name == "COMPLETE.json":
                seen += 1
                if seen == 2:
                    return raw + b" "
            return raw
        with patch.object(protocol, "read_file", side_effect=changing):
            self.reject("SOURCE_CHANGED")

    def test_version_reuse_conflicts_without_replacing_retained_bytes(self):
        first = self.inbox.process(self.package)
        self.change_manifest(lambda m: m.update(scorer_version="other-v1"))
        # Consumer explicitly supports the alternative scorer, so this reaches conflict resolution.
        profile = self.profiles[0].to_dict()
        profile["scorer_versions"].append("other-v1")
        service = ReleaseInbox(self.root / "store", (protocol.SupportedProfile.from_dict(profile),), allow_test_profiles=True)
        ack = service.process(self.package)
        self.assertEqual([ack[k] for k in ("outcome", "reason_code", "state")], EXPECTED["outcomes"]["conflict"])
        self.assertEqual(service.get_release(first["package_id"])["manifest_id"], first["manifest_id"])
        self.assertEqual(hashed(service.read_file(first["package_id"], "manifest.json")), EXPECTED["files"]["manifest.json"])
        self.assertEqual(self.counts(), (1, 11, 2))

    def test_interrupted_write_rolls_back_package_files_and_success_ack(self):
        def interrupted(con, package_id, files):
            path, raw = next(iter(files.items()))
            con.execute("INSERT INTO files VALUES (?,?,?,?)", (package_id, path, hashed(raw), raw))
            raise OSError("synthetic disk interruption")
        with patch.object(self.inbox, "_insert_files", side_effect=interrupted):
            with self.assertRaises(StorageError):
                self.inbox.process(self.package)
        self.assertEqual(self.counts(), (0, 0, 0))
        self.assertEqual(self.inbox.process(self.package)["outcome"], "IMPORTED_INACTIVE")

    def test_process_crash_before_commit_recovers_without_partial_success(self):
        code = '''import sys,os
sys.path[:0]=sys.argv[1:3]
from application.release_inbox import ReleaseInbox,load_profiles
service=ReleaseInbox(sys.argv[3],load_profiles(sys.argv[4]),allow_test_profiles=True)
original=service._insert_files
def crash(con,package_id,files):
    original(con,package_id,files)
    os._exit(19)
service._insert_files=crash
service.process(sys.argv[5])
'''
        result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code, str(ROOT),
                                 str(ROOT / "packages/jse_intelligence_core/src"), str(self.root / "store"),
                                 str(FIXTURES / "profiles.json"), str(self.package)], capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 19, result.stderr)
        self.assertEqual(self.counts(), (0, 0, 0))
        reopened = ReleaseInbox(self.root / "store", self.profiles, allow_test_profiles=True)
        self.assertEqual(reopened.process(self.package)["outcome"], "IMPORTED_INACTIVE")

    def test_concurrent_duplicate_attempts_are_serialized_and_idempotent(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.inbox.process(self.package), range(8)))
        self.assertEqual(sum(a["outcome"] == "IMPORTED_INACTIVE" for a in results), 1)
        self.assertEqual(sum(a["outcome"] == "ALREADY_IMPORTED" for a in results), 7)
        self.assertEqual(len({a["ack_id"] for a in results}), 8)
        self.assertEqual(self.counts(), (1, 11, 8))

    def test_immutable_sql_rows_and_unrelated_database_refusal(self):
        self.inbox.process(self.package)
        with closing(sqlite3.connect(self.inbox.path)) as con:
            for table in ("packages", "files", "acknowledgements"):
                with self.assertRaises(sqlite3.IntegrityError):
                    con.execute(f"DELETE FROM {table}")
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("UPDATE packages SET state='ACTIVE'")
        other = self.root / "other-store"
        other.mkdir()
        with closing(sqlite3.connect(other / "inbox-registry.sqlite3")) as con:
            con.execute("CREATE TABLE unrelated (value TEXT)")
        with self.assertRaises(StorageError):
            ReleaseInbox(other)

    def test_no_runtime_activation_scorer_or_research_summary_change(self):
        from application.opportunities.local_backtest_reports import read_summary, COUNTERS, digest as report_digest
        from domain.strategy.registry import DEFAULT_STRATEGY_REGISTRY
        profile_before = copy.deepcopy(DEFAULT_STRATEGY_REGISTRY.resolve("jse_swing_3_5d", "1.0.1"))
        before = score_news("Sasol profits rise").to_dict()
        reports = self.root / "reports"
        reports.mkdir()
        payload = dict(schema="local-backtest-dashboard-v1", b5_outcome="PARTIAL_CLOSED",
                       evidence_date="2026-01-01", window=["2026-01-01", "2026-01-01"],
                       counters={k: 0 for k in COUNTERS},
                       input_hashes={k: "a" * 64 for k in ("status", "comparison", "reference")})
        (reports / "dashboard-summary.json").write_text(json.dumps(dict(payload=payload, sha256=report_digest(payload))))
        report_before = read_summary(reports)
        with patch("socket.create_connection", side_effect=AssertionError("network")):
            ack = self.inbox.process(self.package)
        self.assertEqual(score_news("Sasol profits rise").to_dict(), before)
        self.assertEqual(read_summary(reports), report_before)
        self.assertEqual(DEFAULT_STRATEGY_REGISTRY.resolve("jse_swing_3_5d", "1.0.1"), profile_before)
        self.assertEqual(self.inbox.get_release(ack["package_id"])["state"], "INACTIVE")
        self.assertNotIn("backtrader", sys.modules)
        self.assertNotIn("vectorbt", sys.modules)

    def test_explicit_cli_no_test_fallback_and_no_embedded_support_registry(self):
        args = [sys.executable, "-B", str(ROOT / "scripts/import_radar_release.py"),
                "--package", str(self.package), "--store", str(self.root / "cli-store"),
                "--profiles", str(FIXTURES / "profiles.json")]
        denied = subprocess.run(args, capture_output=True, text=True, timeout=20)
        self.assertEqual(denied.returncode, 3, denied.stderr)
        self.assertEqual(json.loads(denied.stdout)["reason_code"], "TEST_PROFILE_DISABLED")
        accepted = subprocess.run(args + ["--allow-test-profiles"], capture_output=True, text=True, timeout=20)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout)["outcome"], "IMPORTED_INACTIVE")
        embedded = self.package / "profiles.json"
        shutil.copyfile(FIXTURES / "profiles.json", embedded)
        args[-1] = str(embedded)
        self.assertEqual(subprocess.run(args, capture_output=True, timeout=20).returncode, 4)

    def test_file_count_total_bytes_and_json_node_limits(self):
        for index in range(65):
            (self.package / f"extra{index}.json").write_text('{}')
        self.reject("LIMIT_EXCEEDED")
        for path in self.package.glob("extra*.json"):
            path.unlink()
        env = self.load("envelope.json")
        additions = []
        for index in range(10):
            raw = encoded(dict(schema_version="radar-inert-data/1", data="x" * (220 * 1024)))
            name, rid = f"artifacts/large{index}.json", f"large:{index}"
            (self.package / name).write_bytes(raw)
            env["artifacts"].append(dict(reference_id=rid, path=name, format="json-data/1",
                                         byte_hash=hashed(raw), canonical_id=None))
            additions.append(dict(reference_id=rid, content_hash=hashed(raw)))
        self.seal(env)
        self.change_manifest(lambda m: m["content_references"].extend(additions))
        self.reject("LIMIT_EXCEEDED")
        with self.assertRaises(protocol.Rejection):
            protocol.parse_json(encoded([0] * (protocol.MAX_NODES + 1)))

    def test_fresh_process_forbids_runtime_provider_engine_and_external_db_access(self):
        code = r'''
import sys
from pathlib import Path
sys.path[:0]=sys.argv[1:3]
store=Path(sys.argv[3])
blocked={'app','domain','persistence','market_intelligence','data_pipeline','jse_adapter',
         'sentiment_analyzer','sentiment_providers','dotenv','requests','ollama','openai','backtrader','vectorbt','psycopg'}
class Guard:
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in blocked: raise AssertionError('forbidden import '+fullname)
sys.meta_path.insert(0,Guard())
def audit(event,args):
    if event.startswith(('socket.','subprocess.','os.system')): raise AssertionError(event)
    if event=='sqlite3.connect' and not Path(args[0]).is_relative_to(store): raise AssertionError('external database')
    if event=='open':
        path,mode,flags=args
        if isinstance(path,(str,bytes)):
            if '.env' in str(path): raise AssertionError('private config read')
            if ((mode and any(c in mode for c in 'wax+')) or (flags and flags & (1|2|64|512))) and not Path(path).is_relative_to(store):
                raise AssertionError('outside store write')
sys.addaudithook(audit)
from application.release_inbox import ReleaseInbox,load_profiles
ack=ReleaseInbox(store,load_profiles(sys.argv[4]),allow_test_profiles=True).process(sys.argv[5])
assert ack['outcome']=='IMPORTED_INACTIVE' and ack['state']=='INACTIVE'
assert not blocked & set(sys.modules)
print('isolated inactive ingestion PASS')
'''
        result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code, str(ROOT),
                                 str(ROOT / "packages/jse_intelligence_core/src"), str(self.root / "isolated-store"),
                                 str(FIXTURES / "profiles.json"), str(self.package)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
