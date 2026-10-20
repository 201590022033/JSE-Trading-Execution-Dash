"""Explicit reviewed-release selection and append-only current-radar decisions."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sqlite3
import uuid

from application.release_inbox import StorageError
from application.release_inbox.protocol import Rejection, canonical, digest, plain_path
from jse_intelligence_core import ContractError
from .kernel import (RadarError, bounded, closed, evaluate_current, load_release,
                     require, timestamp, validate_snapshot)

APP_ID = 0x4A535233


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RadarReleases:
    def __init__(self, inbox, journal_dir, *, issuer_catalog, allow_test_releases=False):
        require(type(allow_test_releases) is bool, "INVALID_CONFIGURATION")
        self.inbox = inbox
        self.root = plain_path(journal_dir)
        require(self.root != inbox.root and self.root not in inbox.root.parents
                and inbox.root not in self.root.parents, "SEPARATE_JOURNAL_REQUIRED")
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "radar-journal.sqlite3"
        self.catalog = bounded(issuer_catalog)
        require(type(self.catalog) is dict and len(self.catalog) <= 256 and all(
            type(k) is str and type(v) is str and 4 <= len(v.strip()) <= 150 and v == v.strip()
            for k, v in self.catalog.items()), "INVALID_ISSUER_CATALOG")
        self.allow_test = allow_test_releases
        self.ready = False
        with self._db() as con:
            con.execute("BEGIN IMMEDIATE")
            app = con.execute("PRAGMA application_id").fetchone()[0]
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if app == 0 and not tables and con.execute("PRAGMA user_version").fetchone()[0] == 0:
                con.execute(f"PRAGMA application_id={APP_ID}")
                con.execute("PRAGMA user_version=1")
                con.execute("CREATE TABLE records (seq INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL, kind TEXT NOT NULL, lane TEXT NOT NULL, body TEXT NOT NULL)")
                for action in ("UPDATE", "DELETE"):
                    con.execute(f"CREATE TRIGGER immutable_{action} BEFORE {action} ON records BEGIN SELECT RAISE(ABORT,'immutable radar event'); END")
            else:
                require(app == APP_ID and tables == {"records"} and con.execute("PRAGMA user_version").fetchone()[0] == 1, "UNRECOGNIZED_JOURNAL")
        self.ready = True

    @contextmanager
    def _db(self):
        plain_path(self.root)
        for suffix in ("", "-journal", "-wal", "-shm"):
            path = plain_path(str(self.path) + suffix)
            require(not path.exists() or (path.is_file() and path.stat().st_nlink == 1), "UNSAFE_JOURNAL")
        con = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            con.execute("PRAGMA synchronous=FULL")
            if self.ready:
                require(con.execute("PRAGMA application_id").fetchone()[0] == APP_ID
                        and con.execute("PRAGMA user_version").fetchone()[0] == 1, "UNRECOGNIZED_JOURNAL")
            with con:
                yield con
        finally:
            con.close()

    @staticmethod
    def _lane(scope_id, role):
        return canonical(dict(scope_id=scope_id, role=role))

    @staticmethod
    def _insert(con, kind, lane, body, event_id=None):
        event_id = event_id or str(uuid.uuid4())
        row = con.execute("SELECT body FROM records WHERE event_id=?", (event_id,)).fetchone()
        if row:
            return json.loads(row[0])
        body = {**body, "schema_version": "radar-event/1", "event_id": event_id, "kind": kind}
        raw = canonical(body)
        require(len(raw.encode()) <= 1024 * 1024, "EVENT_TOO_LARGE")
        con.execute("INSERT INTO records(event_id,kind,lane,body) VALUES (?,?,?,?)", (event_id, kind, lane, raw))
        return body

    def events(self):
        with self._db() as con:
            return [json.loads(r[0]) for r in con.execute("SELECT body FROM records ORDER BY seq")]

    def _accepted(self, package_id, con, event_id=None):
        for (raw,) in con.execute("SELECT body FROM records WHERE kind='ACCEPT' ORDER BY seq DESC"):
            body = json.loads(raw)
            if body["package_id"] == package_id and (event_id is None or body["event_id"] == event_id):
                return body
        raise RadarError("NOT_ACCEPTED")

    def accept(self, review):
        now = utc_now()
        review = bounded(review)
        closed(review, ("schema_version", "review_id", "reviewer", "approved", "package_id", "manifest_id",
                        "model_id", "parity_id", "criteria", "source_ids", "evidence_ids"))
        require(review["schema_version"] == "radar-review/1" and review["approved"] is True, "REVIEW_REQUIRED")
        for field in ("review_id", "reviewer"):
            require(type(review[field]) is str and 1 <= len(review[field].strip()) <= 100, "REVIEW_REQUIRED")
        record, manifest, model, model_hash, parity_hash = load_release(
            self.inbox, review["package_id"], review["model_id"], review["parity_id"])
        require(not record["profile"]["test_only"] or self.allow_test, "TEST_RELEASE_DISABLED")
        require(review["manifest_id"] == manifest.canonical_id, "REVIEW_IDENTITY_MISMATCH")
        require(review["criteria"] == ("attention_relevance" if manifest.role == "attention" else "directional_outcomes"), "WRONG_REVIEW_CRITERIA")
        for field in ("source_ids", "evidence_ids"):
            require(type(review[field]) is list and 1 <= len(review[field]) <= 64
                    and all(type(x) is str and x for x in review[field]) and len(set(review[field])) == len(review[field]), "REVIEW_REQUIRED")
        require(set(review["evidence_ids"]) == {r.content_hash for r in manifest.evidence_references}, "REVIEW_EVIDENCE_MISMATCH")
        require(all(v.instrument_id in self.catalog for v in manifest.vehicles), "UNSUPPORTED_ISSUER")
        lane = self._lane(manifest.scope.scope_id, manifest.role)
        key = "accept-" + digest(canonical(review).encode()).split(":")[1]
        with self._db() as con:
            con.execute("BEGIN IMMEDIATE")
            return self._insert(con, "ACCEPT", lane, dict(received_at=now, package_id=review["package_id"],
                manifest_id=manifest.canonical_id, model_hash=model_hash, parity_hash=parity_hash,
                model_id=review["model_id"], parity_id=review["parity_id"], role=manifest.role,
                scope_id=manifest.scope.scope_id, review=review, test_only=record["profile"]["test_only"]), key)

    def select(self, package_id, *, effective_at, expected_previous, reason, rollback=False):
        now = utc_now()
        require(type(reason) is str and 1 <= len(reason.strip()) <= 300 and type(rollback) is bool, "REASON_REQUIRED")
        require(timestamp(effective_at) >= timestamp(now), "BACKDATED_SELECTION")
        with self._db() as con:
            con.execute("BEGIN IMMEDIATE")
            accepted = self._accepted(package_id, con)
            require(not accepted["test_only"] or self.allow_test, "TEST_RELEASE_DISABLED")
            load_release(self.inbox, package_id, accepted["model_id"], accepted["parity_id"])
            lane = self._lane(accepted["scope_id"], accepted["role"])
            rows = [json.loads(r[0]) for r in con.execute(
                "SELECT body FROM records WHERE lane=? AND kind IN ('SELECT','ROLLBACK') ORDER BY seq", (lane,))]
            previous = rows[-1] if rows else None
            require(expected_previous == (previous["event_id"] if previous else None), "SELECTION_CONFLICT")
            require(previous is None or timestamp(effective_at) > timestamp(previous["effective_at"]), "NON_MONOTONIC_SELECTION")
            if rollback:
                require(any(r["package_id"] == package_id for r in rows), "NOT_PRIOR_SELECTION")
            return self._insert(con, "ROLLBACK" if rollback else "SELECT", lane, dict(
                received_at=now, effective_at=timestamp(effective_at).isoformat().replace("+00:00", "Z"),
                package_id=package_id, acceptance_id=accepted["event_id"], previous_id=expected_previous,
                scope_id=accepted["scope_id"], role=accepted["role"], reason=reason,
                test_only=accepted["test_only"]))

    def evaluate(self, snapshot, policy, *, role="attention"):
        now = utc_now()
        require(role in ("attention", "directional"), "POLICY_REQUIRES_STRATEGY_RELEASE")
        snapshot, evidence, document, snapshot_id = validate_snapshot(snapshot)
        policy = bounded(policy)
        lane = self._lane(snapshot["scope_id"], role)
        # Selection and decision commit share a write transaction, preventing a
        # selection change between the read and its attributed decision record.
        with self._db() as con:
            con.execute("BEGIN IMMEDIATE")
            rows = [json.loads(r[0]) for r in con.execute(
                "SELECT body FROM records WHERE lane=? AND kind IN ('SELECT','ROLLBACK') ORDER BY seq DESC", (lane,))]
            selected = next((r for r in rows if timestamp(r["effective_at"]) <= timestamp(now)), None)
            result = dict(received_at=now, evaluated_at=now, scope_id=snapshot["scope_id"], role=role,
                          snapshot_id=snapshot_id, snapshot=snapshot, source_policy=policy,
                          selection_id=selected["event_id"] if selected else None,
                          selection_effective_at=selected["effective_at"] if selected else None,
                          acceptance_id=selected["acceptance_id"] if selected else None,
                          package_id=selected["package_id"] if selected else None,
                          test_only=selected["test_only"] if selected else None,
                          outcome="NO_RELEASE", reason_code="NO_EFFECTIVE_RELEASE", score=None,
                          direction=None, policy_input=False, order_intent=None)
            if selected:
                try:
                    accepted = self._accepted(selected["package_id"], con, selected["acceptance_id"])
                    require(not accepted["test_only"] or self.allow_test, "TEST_RELEASE_DISABLED")
                    record, manifest, model, mh, ph = load_release(self.inbox, selected["package_id"], accepted["model_id"], accepted["parity_id"])
                    require(mh == accepted["model_hash"] and ph == accepted["parity_hash"], "ACCEPTANCE_INTEGRITY")
                    scored = evaluate_current(manifest, model, snapshot, evidence, document, policy,
                                              self.catalog, accepted["review"]["source_ids"], timestamp(now))
                    result.update(scored, outcome="ALERT" if scored["alert"] else "NO_ALERT", reason_code="SCORED",
                                  manifest_id=manifest.canonical_id, release_version=manifest.release_version,
                                  model_hash=mh, weight_origin=model["weight_origin"], test_only=accepted["test_only"])
                except (RadarError, Rejection, StorageError, ContractError) as exc:
                    result.update(outcome="UNAVAILABLE", reason_code=str(exc))
            return self._insert(con, "DECISION", lane, result)


class CurrentRadarAdapter:
    """Explicit projection over supplied current packets; never acquires or trades."""
    def __init__(self, releases):
        self.releases = releases

    def score_current(self, snapshots, source_policies, *, role="attention"):
        require(type(snapshots) is list and len(snapshots) <= 100 and type(source_policies) is dict, "BOUNDED_BATCH_REQUIRED")
        results = []
        for snapshot in snapshots:
            require(type(snapshot) is dict and type(snapshot.get("evidence")) is dict, "INVALID_EVIDENCE")
            source_id = snapshot.get("evidence", {}).get("source_id")
            policy = source_policies.get(source_id, dict(source_id=source_id, enabled=False,
                                                        admissible=False, observed_at=utc_now()))
            results.append(self.releases.evaluate(snapshot, policy, role=role))
        return dict(schema_version="current-radar-projection/1", items=results,
                    trading_controls=False, changes_strategy=False)
