"""Offline interchange oracles; fixtures are synthetic, never runtime evidence."""
import copy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT / "packages" / "jse_intelligence_core"
sys.path.insert(0, str(PACKAGE / "src"))
from jse_intelligence_core import (  # noqa: E402
    ArtifactReference, ContractError, EvidenceReference, InstrumentPermission,
    PublicationClock, RadarReleaseManifest, SectorScope,
)

FIXTURES = json.loads((PACKAGE / "fixtures" / "v1.json").read_text(encoding="utf-8"))
CLASSES = {c.__name__: c for c in (SectorScope, EvidenceReference, RadarReleaseManifest)}


class SharedContractTests(unittest.TestCase):
    def test_fixed_independent_serialization_and_hash_oracles(self):
        # The committed expected text/digests were constructed without importing core.
        for example in FIXTURES["accepted"]:
            with self.subTest(example=example["name"]):
                cls = CLASSES[example["contract"]]
                payload = example["payload"]
                oracle = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                self.assertEqual(oracle, example["canonical_json"])
                self.assertEqual("sha256:" + hashlib.sha256(oracle.encode()).hexdigest(), example["canonical_id"])
                obj = cls.from_json(json.dumps(payload), expected_id=example["canonical_id"])
                self.assertEqual(obj.canonical_json(), example["canonical_json"])
                self.assertEqual(obj.canonical_id, example["canonical_id"])
                self.assertEqual(obj.to_dict(), payload)
                self.assertEqual(cls.from_dict(obj.to_dict()), obj)

    def test_fixed_rejection_fixtures(self):
        for example in FIXTURES["rejected"]:
            with self.subTest(example=example["name"]):
                with self.assertRaises(ContractError):
                    CLASSES[example["contract"]].from_dict(example["payload"])

    def test_closed_schema_all_levels_and_versions(self):
        for example in FIXTURES["accepted"][:3]:
            cls, base = CLASSES[example["contract"]], example["payload"]
            for key in base:
                invalid = copy.deepcopy(base)
                del invalid[key]
                with self.subTest(contract=cls.__name__, missing=key), self.assertRaises(ContractError):
                    cls.from_dict(invalid)
            for version in (None, 1, True, "1", base["schema_version"] + ".1"):
                with self.assertRaises(ContractError):
                    cls.from_dict({**base, "schema_version": version})
            with self.assertRaises(ContractError):
                cls.from_dict({**base, "activate": True})
        scope = copy.deepcopy(FIXTURES["accepted"][0]["payload"])
        scope["universe"]["extra"] = 1
        with self.assertRaises(ContractError):
            SectorScope.from_dict(scope)
        evidence = copy.deepcopy(FIXTURES["accepted"][1]["payload"])
        evidence["publication"]["extra"] = 1
        with self.assertRaises(ContractError):
            EvidenceReference.from_dict(evidence)

    def test_clock_rejects_naive_ambiguous_and_false_exact(self):
        for value in ("2026-10-20T09:00:00", "2026-10-20", "2026-10-20T09:00:00-00:00",
                      "2026-10-20T09:00:00+01:60", "2026-10-20T25:00:00Z", 123, None):
            with self.subTest(value=value), self.assertRaises(ContractError):
                PublicationClock(value=value, precision="exact", timezone_state="offset_known", basis="source_asserted")
        for change in ({"timezone_state": "ambiguous"}, {"timezone_state": "unknown"},
                       {"basis": "unverified"}, {"precision": "date"}, {"precision": "unknown"}):
            with self.assertRaises(ContractError):
                PublicationClock(**{**dict(value="2026-10-20T09:00:00Z", precision="exact",
                                          timezone_state="offset_known", basis="source_asserted"), **change})

    def test_offset_equivalence_and_actual_receipt_chronology(self):
        evidence = EvidenceReference.from_dict(FIXTURES["accepted"][1]["payload"])
        same = replace(evidence, acquired_at="2026-10-20T11:01:00+02:00")
        self.assertEqual(same.canonical_id, evidence.canonical_id)
        for change in ({"received_at": "2026-10-20T09:00:59Z"},
                       {"acquired_at": "2026-10-20T08:59:59Z"},
                       {"received_at": "2026-10-20T09:02:00"}):
            with self.assertRaises(ContractError):
                replace(evidence, **change)
        # Reconstruction never replaces actual acquisition/receipt with an old release date.
        old = replace(evidence, reconstruction_state="reconstructed",
                      publication=PublicationClock(value="2000-01-01", precision="date",
                                                   timezone_state="unknown", basis="source_asserted"))
        self.assertEqual(old.acquired_at, evidence.acquired_at)
        self.assertEqual(old.received_at, evidence.received_at)

    def test_scope_and_product_isolation(self):
        scope = SectorScope.from_dict(FIXTURES["accepted"][0]["payload"])
        self.assertTrue(scope.permits("JSE:SYNTH_BANK", "cash_share"))
        for instrument, product in (("context:USDZAR", "currency_product"),
                                    ("JSE:SYNTH_BANK", "equity_etf"), (None, "cash_share"),
                                    ("JSE:OTHER", "cash_share")):
            self.assertFalse(scope.permits(instrument, product))
        for value in (None, (), [], "all"):
            with self.assertRaises(ContractError):
                replace(scope, allowed_instruments=value)
        with self.assertRaises(ContractError):
            replace(scope, allowed_instruments=scope.allowed_instruments * 2)
        with self.assertRaises(ContractError):
            replace(scope, context_references=(ArtifactReference(reference_id="JSE:SYNTH_BANK",
                                                                content_hash="sha256:" + "0" * 64),))
        with self.assertRaises(ContractError):
            InstrumentPermission(instrument_id="*", product_type="cash_share")
        with self.assertRaises(ContractError):
            InstrumentPermission(instrument_id="JSE:X", product_type="index_reference")

    def test_deep_immutability_and_detached_serialization(self):
        release = RadarReleaseManifest.from_dict(FIXTURES["accepted"][2]["payload"])
        before = release.canonical_id
        for obj, key, value in ((release, "role", "policy"), (release.scope, "scope_id", "other"),
                                (release.scope.universe, "as_of", "2000-01-01"),
                                (release.vehicles[0], "product_type", "cfd")):
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, key, value)
        data = release.to_dict()
        data["scope"]["allowed_instruments"].clear()
        self.assertEqual(release.canonical_id, before)
        self.assertFalse(hasattr(release, "__dict__"))
        with self.assertRaises(ContractError):
            replace(release, vehicles=list(release.vehicles))

    def test_hash_and_identity_tampering(self):
        for bad in ("", "a" * 64, "sha256:" + "A" * 64, "md5:" + "0" * 64, None, 1):
            with self.assertRaises(ContractError):
                ArtifactReference(reference_id="synthetic", content_hash=bad)
        example = FIXTURES["accepted"][2]
        changed = {**example["payload"], "release_version": "0.1.1"}
        with self.assertRaises(ContractError):
            RadarReleaseManifest.from_dict(changed, expected_id=example["canonical_id"])
        with self.assertRaises(ContractError):
            SectorScope.from_json('{"scope_id":"a","scope_id":"b"}')

    def test_release_roles_and_exact_compatibility(self):
        release = RadarReleaseManifest.from_dict(FIXTURES["accepted"][2]["payload"])
        for role in ("attention", "directional", "policy"):
            self.assertEqual(replace(release, role=role).role, role)
        for role in ("trade", "ATTENTION", "", None, ["attention", "policy"]):
            with self.assertRaises(ContractError):
                replace(release, role=role)
        for changes in ({"vehicles": (InstrumentPermission(instrument_id="context:USDZAR", product_type="currency_product"),)},
                        {"horizons": ("any",)}, {"content_references": ()}, {"evidence_references": ()},
                        {"scorer_version": "*"}, {"scope": None}):
            with self.assertRaises(ContractError):
                replace(release, **changes)
        args = dict(feature_schema_version=release.feature_schema_version,
                    model_format_version=release.model_format_version, runtime_api_version=release.runtime_api_version)
        release.require_compatibility(**args)
        for key in args:
            with self.assertRaises(ContractError):
                release.require_compatibility(**{**args, key: "unsupported-v2"})

    def test_correction_requires_original_link(self):
        evidence = EvidenceReference.from_dict(FIXTURES["accepted"][1]["payload"])
        with self.assertRaises(ContractError):
            replace(evidence, revision_kind="correction")
        with self.assertRaises(ContractError):
            replace(evidence, revision_kind="correction", original_reference=ArtifactReference(
                reference_id=evidence.evidence_id, content_hash=evidence.content_hash))
        with self.assertRaises(ContractError):
            replace(evidence, original_reference=ArtifactReference(reference_id="old", content_hash=evidence.content_hash))

    def test_import_and_validation_in_fresh_isolated_process(self):
        code = r'''
import sys
sys.path.insert(0, sys.argv[1])
import json
from pathlib import Path
examples = json.loads(Path(sys.argv[2]).read_text())['accepted']
forbidden = ('app', 'application', 'domain', 'persistence', 'market_intelligence',
             'sentiment_analyzer', 'sentiment_providers', 'dotenv', 'requests', 'sqlite3', 'psycopg', 'ollama', 'openai')
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in forbidden:
            raise AssertionError('runtime import: ' + fullname)
sys.meta_path.insert(0, Guard())
def audit(event, args):
    if event.startswith(('socket.', 'subprocess.', 'sqlite3.', 'os.system')):
        raise AssertionError('side effect: ' + event)
    if event == 'open':
        path, mode, flags = args
        name = str(path).lower()
        if '.env' in name or name.endswith(('.db', '.sqlite', '.sqlite3')):
            raise AssertionError('runtime file read')
        if (mode and any(c in mode for c in 'wax+')) or (flags and flags & (1 | 2 | 64 | 512)):
            raise AssertionError('file write')
sys.addaudithook(audit)
import jse_intelligence_core as core
for item in examples:
    obj = getattr(core, item['contract']).from_dict(item['payload'], expected_id=item['canonical_id'])
    assert obj.canonical_json() == item['canonical_json']
assert not set(forbidden) & set(sys.modules)
print('isolated import and validation PASS')
'''
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code,
                                     str(PACKAGE / "src"), str(PACKAGE / "fixtures" / "v1.json")],
                                    cwd=folder, capture_output=True, text=True, timeout=20,
                                    env={k: v for k, v in os.environ.items() if k in ("SystemRoot", "WINDIR")})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
