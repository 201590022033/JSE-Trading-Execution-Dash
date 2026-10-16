"""Durable scientific registry over the existing immutable record store.

No schema initialization, runtime activation or execution authority lives here.
The bounded registry fails closed at capacity; it never validates partial lineage.
"""
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from math import isfinite

from domain.contracts.trade import MetricContext
from domain.evaluation.experiment import (
    ArtifactReference, DataBoundary, DecisionType, ExperimentDecision,
    ExperimentDefinition, ExperimentMode, ExperimentRepository, ExperimentResult,
    ExperimentRun, ExperimentStage, Factor, FactorialDesign,
    InMemoryExperimentRepository, SECRET_KEYS,
)
from domain.evaluation.metrics import MetricResult

SCHEMA = "durable-experiment-record-v1"
_TYPES = {t.__name__: t for t in (
    ArtifactReference, DataBoundary, ExperimentDecision, ExperimentDefinition,
    ExperimentResult, ExperimentRun, Factor, FactorialDesign, MetricContext,
    MetricResult, DecisionType, ExperimentMode, ExperimentStage,
)}
_OPERATIONS = {
    "definition": (ExperimentDefinition, "register_definition", "created_at"),
    "run": (ExperimentRun, "record_run", "completed_at"),
    "result": (ExperimentResult, "record_result", "recorded_at"),
    "decision": (ExperimentDecision, "record_decision", "decided_at"),
}


def _encode(value):
    """Only explicit domain types and finite JSON values; never pickle/import."""
    if isinstance(value, Enum):
        if _TYPES.get(type(value).__name__) is not type(value):
            raise ValueError("unsupported experiment enum")
        return {"type": type(value).__name__, "value": value.value}
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("experiment timestamps must be aware")
        return {"type": "datetime", "value": value.isoformat()}
    if is_dataclass(value):
        if _TYPES.get(type(value).__name__) is not type(value):
            raise ValueError("unsupported experiment record type")
        return {"type": type(value).__name__, "fields": {
            f.name: _encode(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) or k.lower() in SECRET_KEYS for k in value):
            raise ValueError("experiment mappings require non-secret string keys")
        return {"type": "mapping", "items": {k: _encode(v) for k, v in value.items()}}
    if isinstance(value, (tuple, list)):
        return {"type": "tuple" if isinstance(value, tuple) else "list",
                "items": [_encode(v) for v in value]}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and isfinite(value):
        return value
    raise ValueError("unsupported or nonfinite experiment value")


def _decode(value):
    if not isinstance(value, dict):
        if isinstance(value, list):
            raise ValueError("invalid typed experiment payload")
        return value
    kind = value.get("type")
    if kind == "datetime" and set(value) == {"type", "value"}:
        return datetime.fromisoformat(value["value"])
    if kind in {"tuple", "list"} and set(value) == {"type", "items"}:
        items = [_decode(v) for v in value["items"]]
        return tuple(items) if kind == "tuple" else items
    if kind == "mapping" and set(value) == {"type", "items"}:
        return {k: _decode(v) for k, v in value["items"].items()}
    target = _TYPES.get(kind)
    if target and issubclass(target, Enum) and set(value) == {"type", "value"}:
        return target(value["value"])
    if target and is_dataclass(target) and set(value) == {"type", "fields"}:
        return target(**{k: _decode(v) for k, v in value["fields"].items()})
    raise ValueError("unknown experiment payload type")


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


class DurableExperimentRepository:
    """Reference-compatible append-only adapter, with atomic durable validation.

    Use an already initialized StorageRepository and existing PAPER account.
    ``namespace`` isolates registries within that account. Identical calls raise as the reference
    repository does; restart recovery must inspect the existing durable record.
    """
    def __init__(self, storage, *, account_id, namespace="hermes-local-v1", capacity=4999):
        if not isinstance(account_id, str) or not account_id:
            raise ValueError("existing experiment account identity required")
        if not isinstance(namespace, str) or not namespace or len(namespace) > 200:
            raise ValueError("bounded experiment namespace required")
        if isinstance(capacity, bool) or not isinstance(capacity, int) or not 1 <= capacity <= 4999:
            raise ValueError("experiment capacity must be 1..4999")
        if storage.backend not in {"sqlite", "postgresql"}:
            raise ValueError("durable experiment storage required")
        self.storage, self.namespace, self.capacity = storage, namespace, capacity
        self.account_id = account_id
        self._scope = "experiments:" + _digest([account_id, namespace])

    @contextmanager
    def _transaction(self):
        with self.storage.transaction():
            if self.storage.backend == "postgresql":
                lock = int.from_bytes(sha256(self._scope.encode()).digest()[:8], "big", signed=True)
                self.storage._job_sql("SELECT pg_advisory_xact_lock(?)", (lock,), rows=True)
            account = self.storage.paper_account(self.account_id)
            if account is None or account.get("mode") != "PAPER":
                raise ValueError("existing PAPER account required for experiment registry")
            yield

    def _load(self):
        rows = self.storage.paper_records(self.account_id, self._scope,
            as_of=datetime.max.replace(tzinfo=timezone.utc).isoformat(), limit=self.capacity + 1)
        if len(rows) > self.capacity:
            raise ValueError("experiment registry capacity exceeded; complete lineage required")
        rows.sort(key=lambda row: row["sequence"])
        reference = InMemoryExperimentRepository()
        for sequence, row in enumerate(rows, 1):
            record_id = f"{self._scope}:{sequence}"
            if (row.get("schema") != SCHEMA or row.get("namespace") != self.namespace
                    or row.get("sequence") != sequence
                    or row.get("account_id") != self.account_id
                    or row.get("record_id") != record_id
                    or row.get("kind") != self._scope
                    or self.storage.paper_record(record_id) != row):
                raise ValueError("invalid experiment registry sequence or identity")
            body = {k: v for k, v in row.items() if k != "sha256"}
            if row.get("sha256") != _digest(body):
                raise ValueError("experiment registry checksum mismatch")
            operation = _OPERATIONS.get(row.get("operation"))
            if operation is None:
                raise ValueError("unknown experiment registry operation")
            record = _decode(row["record"])
            if type(record) is not operation[0] or _encode(record) != row["record"]:
                raise ValueError("noncanonical experiment registry payload")
            getattr(reference, operation[1])(record)
        return reference, len(rows)

    def _append(self, operation, record):
        expected, method, _ = _OPERATIONS[operation]
        if type(record) is not expected:
            raise ValueError("incorrect experiment record type")
        encoded = _encode(record)
        with self._transaction():
            reference, count = self._load()
            if count >= self.capacity:
                raise ValueError("experiment registry capacity reached")
            getattr(reference, method)(record)
            envelope = {"schema": SCHEMA, "namespace": self.namespace,
                        "sequence": count + 1, "operation": operation, "record": encoded,
                        "account_id": self.account_id, "kind": self._scope,
                        "record_id": f"{self._scope}:{count + 1}",
                        "stored_at": datetime.now(timezone.utc).isoformat()}
            envelope["sha256"] = _digest(envelope)
            self.storage.save_paper_record(f"{self._scope}:{count + 1}", self.account_id,
                self._scope, envelope["stored_at"], envelope)
        return record

    def register_definition(self, definition): return self._append("definition", definition)
    def record_run(self, run): return self._append("run", run)
    def record_result(self, result): return self._append("result", result)
    def record_decision(self, decision): return self._append("decision", decision)

    def _read(self, method, *args, **kwargs):
        with self._transaction():
            reference, _ = self._load()
            return getattr(reference, method)(*args, **kwargs)

    def get_experiment(self, experiment_id, experiment_version):
        return self._read("get_experiment", experiment_id, experiment_version)
    def list_experiments(self): return self._read("list_experiments")
    def get_lineage(self, baseline_id): return self._read("get_lineage", baseline_id)
    def find(self, **criteria): return self._read("find", **criteria)


__all__ = ["ExperimentRepository", "InMemoryExperimentRepository", "DurableExperimentRepository"]
