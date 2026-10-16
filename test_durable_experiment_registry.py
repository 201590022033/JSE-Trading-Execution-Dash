"""Durable contract parity plus restart, atomicity and typed lineage evidence."""
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest

from domain.evaluation.experiment import (
    ArtifactReference, DecisionType, ExperimentDecision, ExperimentStage,
    Factor, FactorialDesign,
)
from domain.evaluation.metrics import MetricResult
from persistence.experiment_repo import DurableExperimentRepository
from persistence.sqlite_repository import SQLiteRepository
from persistence.postgres_repository import PostgresRepository
from test_experiment_registry import ExperimentRegistryTests as _ReferenceTests
from test_postgres_repository_behavior import SQLiteDBAPIForPostgres


class DurableRegistryTests(_ReferenceTests):
    backend = "sqlite"

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "registry.db"
        self.storage = self.make_storage()
        self.storage.create_paper_account("research", {"mode": "PAPER"})
        self.repo = DurableExperimentRepository(self.storage, account_id="research")

    def make_storage(self):
        if self.backend == "sqlite":
            return SQLiteRepository(self.path)
        storage = PostgresRepository("postgresql://fixture", connection=SQLiteDBAPIForPostgres(self.path))
        storage.initialize()
        return storage

    def tearDown(self):
        self.storage.close()
        self.tmp.cleanup()

    def test_restart_roundtrip_complete_typed_records_and_exact_lineage(self):
        lineage = {"strategy_profile_id": "swing", "strategy_profile_version": "1.0.1"}
        self.definition = replace(self.definition, **lineage,
            baseline_artifacts=(ArtifactReference("a", "file:artifact", "a" * 64, "application/json", "abc"),),
            changed_components=("a", "b"), factorial_design=FactorialDesign(
                (Factor("a", ("off", "on")), Factor("b", ("low", "high"))), "interaction", "balanced cells"))
        self.run = replace(self.run, **lineage)
        context = replace(self.ctx, **lineage)
        metric = MetricResult("NET_EXPECTANCY", "v1", -.01, context, 20, 12., 10,
                              "VALID", ("limited",), {"nested": {"ids": ["a", "b"]}}, **lineage)
        self.result = replace(self.result, **lineage, metric_contexts={"net": context},
                              canonical_metrics=(metric,))
        self.ready()
        decision = ExperimentDecision("d1", "e1", "v1", self.t + timedelta(hours=4),
            DecisionType.ACCEPT_FOR_NEXT_STAGE, "independent-reviewer", "continue shadow",
            ("res1",), (), ("limited data",), ExperimentStage.SHADOW, "baseline-next", **lineage)
        self.repo.record_decision(decision)
        before = self.repo.get_experiment("e1", "v1")
        self.storage.close()
        self.storage = self.make_storage()
        self.repo = DurableExperimentRepository(self.storage, account_id="research")
        self.assertEqual(before, self.repo.get_experiment("e1", "v1"))
        self.assertEqual(self.repo.get_lineage("baseline-next"), (decision,))
        self.assertIs(self.repo.get_experiment("e1", "v1")["runs"][0].stage, ExperimentStage.OUT_OF_SAMPLE)
        self.assertEqual(self.repo.get_experiment("e1", "v1")["results"][0].canonical_metrics, (metric,))
        with self.assertRaises(ValueError):
            self.repo.record_run(replace(self.run, run_id="bad", strategy_profile_version="1.0.2"))

    def test_cross_experiment_decision_rejected_and_transaction_does_not_append(self):
        self.ready()
        self.repo.register_definition(replace(self.definition, experiment_id="other"))
        before = self.storage._job_sql("SELECT COUNT(*) FROM paper_records", rows=True)[0][0]
        decision = ExperimentDecision("d", "other", "v1", self.t, DecisionType.REJECT,
                                      "reviewer", "reject", ("res1",), (), (), None)
        with self.assertRaisesRegex(ValueError, "different experiment"):
            self.repo.record_decision(decision)
        self.assertEqual(before, self.storage._job_sql("SELECT COUNT(*) FROM paper_records", rows=True)[0][0])

    def test_no_cached_view_between_adapters_and_namespace_isolation(self):
        other = DurableExperimentRepository(self.storage, account_id="research")
        self.repo.register_definition(self.definition)
        self.assertEqual(other.list_experiments(), (self.definition,))
        with self.assertRaises(ValueError):
            other.register_definition(replace(self.definition, primary_hypothesis="conflicting"))
        separate = DurableExperimentRepository(self.storage, account_id="research", namespace="other")
        self.assertEqual(separate.list_experiments(), ())
        separate.register_definition(self.definition)
        self.assertEqual(separate.list_experiments(), (self.definition,))

    def test_recursive_secret_unsafe_value_and_nonfinite_rejected_before_write(self):
        self.ready()
        for bad in ({"nested": {"password": "do not persist"}}, {"x": float("nan")}, {"x": object()}):
            with self.subTest(value=type(bad["nested"] if "nested" in bad else bad["x"]).__name__):
                with self.assertRaises(ValueError):
                    self.repo.record_result(replace(self.result, result_id="unsafe", uncertainty=bad))
        self.assertEqual(len(self.repo.get_experiment("e1", "v1")["results"]), 1)

    def test_capacity_failure_never_returns_partial_lineage(self):
        tiny = DurableExperimentRepository(self.storage, account_id="research", capacity=1)
        tiny.register_definition(self.definition)
        with self.assertRaisesRegex(ValueError, "capacity"):
            tiny.record_run(self.run)
        self.repo.record_run(self.run)
        with self.assertRaisesRegex(ValueError, "capacity"):
            tiny.list_experiments()

    def test_corrupted_envelope_is_not_silently_accepted(self):
        self.repo.register_definition(self.definition)
        row = self.storage._job_sql("SELECT record_id,payload FROM paper_records", rows=True)[0]
        body = json.loads(row[1]); body["record"]["fields"]["baseline_commit"] = "tampered"
        with self.storage.transaction():
            self.storage._job_sql("UPDATE paper_records SET payload=? WHERE record_id=?", (json.dumps(body), row[0]))
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.repo.list_experiments()

    def test_missing_account_does_not_create_one(self):
        adapter = DurableExperimentRepository(self.storage, account_id="missing")
        with self.assertRaisesRegex(ValueError, "existing PAPER"):
            adapter.register_definition(self.definition)
        self.assertIsNone(self.storage.paper_account("missing"))

    def test_failed_persistence_rolls_back_and_retry_uses_same_sequence(self):
        original = self.storage.save_paper_record
        def interrupted(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("interrupted before commit")
        self.storage.save_paper_record = interrupted
        try:
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.repo.register_definition(self.definition)
        finally:
            self.storage.save_paper_record = original
        self.assertEqual(self.repo.list_experiments(), ())
        self.repo.register_definition(self.definition)
        self.assertEqual(self.repo.list_experiments(), (self.definition,))
        self.assertEqual(self.storage._job_sql("SELECT COUNT(*) FROM paper_records", rows=True)[0][0], 1)

    def test_storage_order_by_timestamp_does_not_reorder_scientific_operations(self):
        self.repo.register_definition(self.definition)
        self.repo.record_run(self.run)
        # The reference accepts a historical recorded_at; durable dependency order
        # is append sequence, never a retrospective time sort or backdated ingest.
        historical_result = replace(self.result, recorded_at=self.t - timedelta(days=2))
        self.repo.record_result(historical_result)
        self.assertEqual(self.repo.get_experiment("e1", "v1")["results"], (historical_result,))
        rows = self.storage._job_sql("SELECT available_at,payload FROM paper_records", rows=True)
        for available_at, payload in rows:
            self.assertGreater(available_at, self.t.isoformat())
            self.assertEqual(available_at, json.loads(payload)["stored_at"])


class PostgresDurableRegistryTests(DurableRegistryTests):
    """SQL behavior double; native PostgreSQL locking requires integration proof."""
    backend = "postgresql"


del _ReferenceTests  # Avoid discovering the imported reference suite twice.


if __name__ == "__main__":
    unittest.main()
