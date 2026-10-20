"""X1b offline parity against hand answers and isolated original AST functions."""
import ast
import copy
from dataclasses import FrozenInstanceError, asdict, dataclass, field
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from typing import Dict, List, Optional
import unittest

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT / "packages" / "jse_intelligence_core"
sys.path.insert(0, str(PACKAGE / "src"))
from jse_intelligence_core import ContractError, detect_mentions, keyword_score, score_news
from jse_intelligence_core import _legacy_news_tables as tables

FIXTURES = json.loads((PACKAGE / "fixtures/legacy-news-v1.json").read_text())
LINEAGE = json.loads((PACKAGE / "fixtures/legacy-news-provenance.json").read_text())


def legacy_namespace():
    """Compile only pinned constants/records/pure functions, never app imports."""
    tree = ast.parse((ROOT / LINEAGE["source_path"]).read_text(encoding="utf-8"))
    selected = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
    for node in tree.body:
        name = (node.targets[0].id if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                else getattr(node, "name", ""))
        if name in LINEAGE["ast_sha256"] or name in ("AssetImpact", "AnalyzedItem"):
            selected.append(node)
    namespace = dict(globals())
    def forbidden(*args, **kwargs):
        raise AssertionError("legacy oracle attempted a provider call")
    namespace["_llm_analyze"] = forbidden
    module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    exec(compile(module, "pinned-legacy-pure-functions", "exec"), namespace)
    return namespace


class LegacyNewsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.legacy = legacy_namespace()

    def test_original_algorithm_nodes_remain_pinned(self):
        source = (ROOT / LINEAGE["source_path"]).read_text(encoding="utf-8")
        found = {}
        for node in ast.parse(source).body:
            name = (node.targets[0].id if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                    else getattr(node, "name", ""))
            if name in LINEAGE["ast_sha256"]:
                found[name] = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
        self.assertEqual(found, LINEAGE["ast_sha256"])

    def test_all_fixed_tables_equal_original_including_order(self):
        for name in ("MACRO_ASSETS", "MACRO_KEYWORDS", "TICKER_ALIASES", "_BULLISH", "_BEARISH", "_LLM_TICKER_MAP"):
            original, ported = self.legacy[name], getattr(tables, name)
            if isinstance(original, dict):
                self.assertEqual(list(original), list(ported))
                original = {k: tuple(v) if isinstance(v, list) else v for k, v in original.items()}
                self.assertEqual(original, dict(ported))
            else:
                self.assertEqual(tuple(original), ported)

    def test_hand_answers_and_old_new_score_parity(self):
        for case in FIXTURES["cases"]:
            with self.subTest(case=case["name"]):
                inp, expected = case["input"], case["expected"]
                item = SimpleNamespace(headline=inp["headline"], text=inp["text"], source="synthetic",
                                       timestamp="2026-10-20T00:00:00Z", url="synthetic:retained-reference",
                                       sentiment_label=SimpleNamespace(value=inp["prior_sentiment"]),
                                       sentiment_score=.99)
                before = copy.deepcopy(inp)
                old = self.legacy["analyze_item"](
                    item, use_llm=True, llm_analyzer=lambda *args: copy.deepcopy(inp["assessment"]))
                old_fields = {key: getattr(old, key) for key in expected if key != "assets"}
                old_fields["assets"] = [asdict(a) for a in old.assets]
                new = score_news(**inp)
                self.assertEqual(old_fields, expected)
                self.assertEqual(new.legacy_fields(), expected)
                self.assertEqual(new.provenance.input_hash, case["input_hash"])
                self.assertEqual(inp, before)

    def test_mention_and_keyword_parity_for_all_lexicon_entries(self):
        texts = [v for aliases in self.legacy["TICKER_ALIASES"].values() for v in aliases]
        texts += [v for words in self.legacy["MACRO_KEYWORDS"].values() for v in words]
        texts += list(self.legacy["_BULLISH"]) + list(self.legacy["_BEARISH"])
        for text in texts:
            with self.subTest(text=text):
                for sample in (text, text.upper(), "prefix" + text + "suffix"):
                    self.assertEqual([asdict(a) for a in detect_mentions(sample)],
                                     [asdict(a) for a in self.legacy["detect_mentions"](sample)])
                    self.assertEqual(keyword_score(sample), self.legacy["_keyword_score"](sample))

    def test_assessed_alias_map_and_clamps_match_legacy(self):
        for alias, name in self.legacy["_LLM_TICKER_MAP"].items():
            assessment = {"score": -3, "assets": [{"name": alias.lower(), "direction": -2, "strength": 5}]}
            result = score_news("", assessment=assessment)
            self.assertEqual(result.score, -1)
            self.assertEqual(asdict(result.assets[0]), dict(name=name, direction=-1, strength=1.0))

    def test_provenance_distinguishes_fixed_assessed_and_learned(self):
        fixed = score_news("Sasol profits rise")
        assessed = score_news("Sasol profits rise", assessment={"score": .6, "_provider": "synthetic"})
        self.assertEqual(fixed.provenance.score_origin, "fixed_keyword_heuristic")
        self.assertEqual(fixed.provenance.asset_origin, "fixed_substring_heuristic")
        self.assertEqual(assessed.provenance.score_origin, "provider_assessed")
        self.assertEqual(assessed.provenance.asset_origin, "provider_assessed_with_fixed_aliases")
        for result in (fixed, assessed):
            self.assertFalse(result.provenance.learned_weights)
            self.assertEqual(result.provenance.scorer_version, FIXTURES["scorer_version"])
            self.assertEqual(result.provenance.source_revision, LINEAGE["source_revision"])
            self.assertEqual(result.provenance.source_path, LINEAGE["source_path"])
        # Caller-supplied metadata cannot impersonate learned coefficients or a new scorer.
        forged = score_news("x", assessment={"score": .2, "learned_weights": True,
                                              "score_origin": "learned", "scorer_version": "forged"})
        self.assertFalse(forged.provenance.learned_weights)
        self.assertEqual(forged.provenance.scorer_version, FIXTURES["scorer_version"])

    def test_output_and_tables_are_immutable_and_input_detached(self):
        packet = {"score": .6, "assets": [{"name": "SOL", "direction": 1, "strength": .7}]}
        result = score_news("Sasol", assessment=packet)
        before = result.to_dict()
        packet["assets"].clear()
        self.assertEqual(result.to_dict(), before)
        for obj, name, value in ((result, "score", 0), (result.assets[0], "strength", 0),
                                 (result.provenance, "learned_weights", True)):
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, name, value)
        with self.assertRaises(TypeError):
            tables.TICKER_ALIASES["NEW"] = ("new",)
        detached = result.to_dict()
        detached["assets"].clear()
        self.assertEqual(result.to_dict(), before)

    def test_invalid_boundary_inputs_reject_without_calling_runtime(self):
        for changes in ({"headline": None}, {"text": 5}, {"assessment": []},
                        {"prior_sentiment": "unknown"}, {"assessment": {"score": float("nan")}},
                        {"assessment": {"score": float("inf")}}, {"assessment": {"assets": "SOL"}},
                        {"assessment": {"assets": [None]}}, {"assessment": {"_provider": []}},
                        {"assessment": {"ignored": object()}}):
            with self.subTest(changes=changes), self.assertRaises(ContractError):
                score_news(**{**dict(headline="synthetic"), **changes})
        for func in (detect_mentions, keyword_score):
            with self.assertRaises(ContractError):
                func(None)

    def test_pure_installed_style_process_scores_without_application(self):
        code = r'''
import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
fixtures=json.loads(Path(sys.argv[2]).read_text())
blocked={'app','application','domain','market_intelligence','persistence','sentiment_analyzer',
         'sentiment_providers','data_pipeline','jse_adapter','dotenv','requests','sqlite3','psycopg','ollama','openai'}
class Guard:
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in blocked: raise AssertionError('app import: '+fullname)
sys.meta_path.insert(0,Guard())
def audit(event,args):
    if event.startswith(('socket.','subprocess.','sqlite3.','os.system')): raise AssertionError(event)
    if event=='open':
        path,mode,flags=args
        if '.env' in str(path).lower() or str(path).endswith(('.db','.sqlite')): raise AssertionError('private read')
        if (mode and any(c in mode for c in 'wax+')) or (flags and flags & (1|2|64|512)): raise AssertionError('write')
sys.addaudithook(audit)
from jse_intelligence_core import score_news
for case in fixtures['cases']:
    result=score_news(**case['input'])
    assert result.legacy_fields()==case['expected']
    assert result.provenance.input_hash==case['input_hash']
assert not blocked & set(sys.modules)
print(str(len(fixtures['cases']))+' isolated scoring fixtures PASS')
'''
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", code,
                                     str(PACKAGE / "src"), str(PACKAGE / "fixtures/legacy-news-v1.json")],
                                    cwd=folder, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
