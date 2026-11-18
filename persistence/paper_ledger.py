"""Shared durable PAPER ledger; no backend fallback and no external broker."""
import json
import gzip
import base64
import hashlib
from contextlib import contextmanager
from shadow_learning import timestamp
from domain.strategy.attribution import fields, reference, same_strategy, validate_frozen_profile


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class PaperLedger:
    def save_strategy_definition(self, frozen):
        ref = validate_frozen_profile(frozen)
        if ref is None:
            raise ValueError("exact frozen strategy definition required")
        raw, digest = encode(frozen["strategy_profile_snapshot"]), frozen["strategy_profile_sha256"]
        key = (ref.strategy_profile_id, ref.strategy_profile_version)
        with self.transaction():
            self._job_sql("INSERT INTO strategy_definitions VALUES (?,?,?,?) ON CONFLICT(strategy_profile_id,strategy_profile_version) DO NOTHING",
                          (*key, raw, digest))
            rows = self._job_sql("SELECT payload,sha256 FROM strategy_definitions WHERE strategy_profile_id=? AND strategy_profile_version=?", key, rows=True)
            if tuple(rows[0]) != (raw, digest):
                raise ValueError("strategy definition is immutable; use a new version")

    def strategy_definition(self, strategy_profile_id, strategy_profile_version):
        rows = self._job_sql("SELECT payload,sha256 FROM strategy_definitions WHERE strategy_profile_id=? AND strategy_profile_version=?",
                             (strategy_profile_id, strategy_profile_version), rows=True)
        if not rows:
            return None
        raw, digest = rows[0]
        if hashlib.sha256(raw.encode()).hexdigest() != digest:
            raise ValueError("stored strategy definition checksum mismatch")
        return json.loads(raw)

    def _strategy_record(self, record_id, account_id, kind, payload):
        ref = reference(payload)
        if ref is not None and self.strategy_definition(ref.strategy_profile_id, ref.strategy_profile_version) is None:
            raise ValueError("strategy definition must be registered before records")
        for child in (*payload.get("opportunities", ()), *payload.get("etf_opportunities", ())):
            same_strategy(payload, child)
        for name in ("risk", "approved_intent"):
            if isinstance(payload.get(name), dict):
                same_strategy(payload, payload[name])
        if kind == "input" and ref is not None:
            definition = self.strategy_definition(ref.strategy_profile_id, ref.strategy_profile_version)
            validate_frozen_profile(payload, definition=definition)
        # Parents can live in hot storage or lossless archives. No hot-table FK
        # is used, so moving a snapshot to its archive cannot destroy lineage.
        for name in ("decision_id", "policy_id", "risk_evaluation_id", "entry_fill_record_id", "exit_fill_record_id"):
            parent_id = payload.get(name)
            if not parent_id or parent_id == record_id:
                continue
            parent = self.paper_record(parent_id)
            if parent is not None:
                same_strategy(payload, parent)
            elif ref is not None and ((name == "decision_id" and kind.endswith("outcome")) or
                    (name == "policy_id" and kind in {"risk", "intent"}) or
                    (name == "risk_evaluation_id" and kind == "intent") or
                    name in {"entry_fill_record_id", "exit_fill_record_id"}):
                raise ValueError("attributed record requires its exact durable parent")
        if ref is None:
            return
        self._job_sql("INSERT INTO strategy_record_refs VALUES (?,?,?,?,?) ON CONFLICT(record_id) DO NOTHING",
                      (record_id, account_id, kind, ref.strategy_profile_id, ref.strategy_profile_version))
        row = self._job_sql("SELECT account_id,kind,strategy_profile_id,strategy_profile_version FROM strategy_record_refs WHERE record_id=?", (record_id,), rows=True)[0]
        if tuple(row) != (account_id, kind, ref.strategy_profile_id, ref.strategy_profile_version):
            raise ValueError("immutable strategy record reference conflict")

    def create_paper_account(self, account_id, initial):
        if not account_id or initial.get("mode") != "PAPER":
            raise ValueError("explicit PAPER account required")
        with self.transaction():
            self._job_sql("INSERT INTO paper_accounts VALUES (?,?,?) ON CONFLICT(account_id) DO NOTHING",
                          (account_id, 0, encode(initial)))

    @contextmanager
    def paper_account_transaction(self, account_id):
        with self.transaction():
            suffix = " FOR UPDATE" if self.backend == "postgresql" else ""
            rows = self._job_sql("SELECT revision,payload FROM paper_accounts WHERE account_id=?" + suffix,
                                 (account_id,), rows=True)
            if not rows:
                raise ValueError("paper account not configured")
            revision, raw = rows[0]
            state = json.loads(raw)
            yield state
            changed = self._job_sql(
                "UPDATE paper_accounts SET revision=?,payload=? WHERE account_id=? AND revision=?",
                (revision + 1, encode(state), account_id, revision))
            if changed != 1:
                raise RuntimeError("paper account concurrent update")

    def paper_account(self, account_id):
        rows = self._job_sql("SELECT payload FROM paper_accounts WHERE account_id=?",
                             (account_id,), rows=True)
        return json.loads(rows[0][0]) if rows else None

    def save_paper_record(self, record_id, account_id, kind, available_at, payload):
        at = timestamp(available_at).isoformat()
        serialized = encode(payload)
        with self.transaction():
            archived = self._job_sql("SELECT account_id,kind,available_at,payload_gzip_base64,sha256 FROM paper_record_archives WHERE record_id=?",
                                     (record_id,), rows=True)
            if archived:
                row = archived[0]
                raw = self._decode_archive(row[3], row[4])
                if tuple(row[:3]) != (account_id, kind, at) or raw != serialized:
                    raise ValueError("conflicting immutable archived paper record")
                return
            self._job_sql("INSERT INTO paper_records VALUES (?,?,?,?,?) ON CONFLICT(record_id) DO NOTHING",
                         (record_id, account_id, kind, at, serialized))
            rows = self._job_sql("SELECT account_id,kind,available_at,payload FROM paper_records WHERE record_id=?",
                                 (record_id,), rows=True)
            if tuple(rows[0]) != (account_id, kind, at, serialized):
                raise ValueError("conflicting immutable paper record")
            self._strategy_record(record_id, account_id, kind, payload)

    def paper_record(self, record_id):
        rows = self._job_sql("SELECT payload FROM paper_records WHERE record_id=?", (record_id,), rows=True)
        if rows:
            return json.loads(rows[0][0])
        archived = self._job_sql("SELECT payload_gzip_base64,sha256 FROM paper_record_archives WHERE record_id=?",
                                 (record_id,), rows=True)
        return json.loads(self._decode_archive(*archived[0])) if archived else None

    @staticmethod
    def _decode_archive(compressed, digest):
        raw = gzip.decompress(base64.b64decode(compressed)).decode("utf-8")
        if hashlib.sha256(raw.encode("utf-8")).hexdigest() != digest:
            raise ValueError("paper archive checksum mismatch")
        return raw

    def archive_paper_inputs(self, account_id, *, before, limit=100):
        """Lossless bounded compaction, not evidence deletion; audit reads by ID survive."""
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("bounded archive batch required")
        saved = 0
        with self.paper_account_transaction(account_id) as state:
            rows = self._job_sql("SELECT record_id,kind,available_at,payload FROM paper_records "
                "WHERE account_id=? AND kind IN ('input','ranking') AND available_at<? "
                "ORDER BY available_at,record_id LIMIT ?", (account_id, timestamp(before).isoformat(), limit), rows=True)
            for rid, kind, at, raw in rows:
                if rid == state.get("ranking_record_id"):
                    continue
                # Uncompleted jobs may still need to replay the exact frozen input.
                if kind == "input":
                    payload = json.loads(raw)
                    job_key = payload.get("job_key")
                    job = self._job_sql("SELECT status FROM worker_jobs WHERE job_key=?", (job_key,), rows=True)
                    if not job or job[0][0] != "COMPLETED":
                        continue
                packed = base64.b64encode(gzip.compress(raw.encode("utf-8"), mtime=0)).decode("ascii")
                if len(packed) >= len(raw):
                    continue
                digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                self._job_sql("INSERT INTO paper_record_archives VALUES (?,?,?,?,?,?) ON CONFLICT(record_id) DO NOTHING",
                              (rid, account_id, kind, at, packed, digest))
                restored = self._job_sql("SELECT payload_gzip_base64,sha256 FROM paper_record_archives WHERE record_id=?", (rid,), rows=True)
                if self._decode_archive(*restored[0]) != raw:
                    raise ValueError("archive verification failed")
                self._job_sql("DELETE FROM paper_records WHERE record_id=?", (rid,))
                saved += 1
        return saved

    def paper_records(self, account_id, kind, *, as_of, limit=400, before_record_id=None):
        if not isinstance(limit, int) or not 1 <= limit <= 5000:
            raise ValueError("bounded paper query required")
        if before_record_id is not None:
            if not isinstance(before_record_id, str) or not before_record_id or len(before_record_id) > 160:
                raise ValueError("bounded paper record cursor required")
            at = timestamp(as_of).isoformat()
            rows = self._job_sql(
                "SELECT payload FROM paper_records WHERE account_id=? AND kind=? AND "
                "(available_at<? OR (available_at=? AND record_id<=?)) "
                "ORDER BY available_at DESC,record_id DESC LIMIT ?",
                (account_id, kind, at, at, before_record_id, limit), rows=True)
            return [json.loads(row[0]) for row in rows]
        rows = self._job_sql(
            "SELECT payload FROM paper_records WHERE account_id=? AND kind=? AND available_at<=? "
            "ORDER BY available_at DESC,record_id DESC LIMIT ?",
            (account_id, kind, timestamp(as_of).isoformat(), limit), rows=True)
        return [json.loads(row[0]) for row in rows]
