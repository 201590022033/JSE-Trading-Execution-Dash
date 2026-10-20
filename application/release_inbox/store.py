"""Explicit local inactive store; atomic package + registry + acknowledgement."""
from datetime import datetime, timezone
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import uuid
from types import MappingProxyType

from .protocol import Rejection, SupportedProfile, canonical, digest, plain_path, validate_package

APP_ID = 0x4A534532  # JSE2; never open an application/account database.


class StorageError(RuntimeError):
    """No durable acknowledgement can be claimed; explicit retry is safe."""


class ReleaseInbox:
    def __init__(self, store_dir, profiles=(), *, allow_test_profiles=False):
        if type(allow_test_profiles) is not bool:
            raise ValueError("explicit boolean test-profile policy required")
        self.root = plain_path(store_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "inbox-registry.sqlite3"
        self.profiles = {}
        for value in profiles:
            # Detached, revalidated consumer configuration, never package metadata.
            profile = SupportedProfile.from_dict(value.to_dict())
            if profile.profile_id in self.profiles:
                raise ValueError("duplicate supported profile")
            self.profiles[profile.profile_id] = profile
        self.allow_test_profiles = allow_test_profiles
        self.profiles = MappingProxyType(self.profiles)
        self._initialized = False
        self._initialize()
        self._initialized = True

    @contextmanager
    def _connect(self):
        try:
            plain_path(self.root)
            for suffix in ("", "-journal", "-wal", "-shm"):
                candidate = plain_path(str(self.path) + suffix)
                if candidate.exists() and (not candidate.is_file() or candidate.stat().st_nlink != 1):
                    raise StorageError("unsafe local store file")
        except (Rejection, OSError) as exc:
            raise StorageError("unsafe local store path") from exc
        con = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            con.execute("PRAGMA synchronous=FULL")
            if self._initialized and (con.execute("PRAGMA application_id").fetchone()[0] != APP_ID
                                      or con.execute("PRAGMA user_version").fetchone()[0] != 1):
                raise StorageError("unrecognized local store")
            with con:
                yield con
        finally:
            con.close()

    def _initialize(self):
        try:
            with self._connect() as con:
                con.execute("BEGIN IMMEDIATE")
                app_id = con.execute("PRAGMA application_id").fetchone()[0]
                version = con.execute("PRAGMA user_version").fetchone()[0]
                tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if app_id == 0 and version == 0 and not tables:
                    con.execute(f"PRAGMA application_id={APP_ID}")
                    con.execute("PRAGMA user_version=1")
                    con.execute("""CREATE TABLE packages (
                        package_id TEXT PRIMARY KEY, manifest_id TEXT UNIQUE NOT NULL,
                        release_id TEXT NOT NULL, release_version TEXT NOT NULL,
                        state TEXT NOT NULL CHECK(state='INACTIVE'), manifest_json TEXT NOT NULL,
                        profile_json TEXT NOT NULL, received_at TEXT NOT NULL,
                        UNIQUE(release_id,release_version))""")
                    con.execute("""CREATE TABLE files (
                        package_id TEXT NOT NULL, path TEXT NOT NULL, byte_hash TEXT NOT NULL,
                        body BLOB NOT NULL, PRIMARY KEY(package_id,path))""")
                    con.execute("""CREATE TABLE acknowledgements (
                        ack_id TEXT PRIMARY KEY, body TEXT NOT NULL)""")
                    for table in ("packages", "files", "acknowledgements"):
                        for action in ("UPDATE", "DELETE"):
                            con.execute(f"CREATE TRIGGER immutable_{table}_{action} BEFORE {action} ON {table} "
                                        "BEGIN SELECT RAISE(ABORT,'immutable inbox record'); END")
                elif app_id != APP_ID or version != 1 or tables != {"packages", "files", "acknowledgements"}:
                    raise StorageError("unrecognized local store")
        except (OSError, sqlite3.Error) as exc:
            raise StorageError("local store unavailable") from exc

    def _insert_files(self, con, package_id, files):
        for path, raw in files.items():
            con.execute("INSERT INTO files VALUES (?,?,?,?)", (package_id, path, digest(raw), raw))

    def process(self, package_dir):
        # Actual invocation receipt, independent of every supplied research clock.
        ack = dict(schema_version="radar-inbox-ack/1", ack_id=str(uuid.uuid4()),
                   received_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                   package_id=None, manifest_id=None, release_id=None, release_version=None,
                   profile_id=None, test_only=None, outcome=None, reason_code=None, state=None)
        accepted = None
        try:
            package = plain_path(package_dir)
            if package == self.root or package in self.root.parents or self.root in package.parents:
                raise Rejection("UNSAFE_PATH")
            accepted = validate_package(package, self.profiles, self.allow_test_profiles, ack)
        except Rejection as exc:
            ack.update(outcome="PENDING" if exc.code == "INCOMPLETE" else "REJECTED", reason_code=exc.code)
        except OSError:
            ack.update(outcome="REJECTED", reason_code="READ_FAILED")
        try:
            with self._connect() as con:
                con.execute("BEGIN IMMEDIATE")
                if accepted is not None:
                    manifest, profile, files = accepted
                    same = con.execute("SELECT package_id FROM packages WHERE package_id=?", (ack["package_id"],)).fetchone()
                    reused = con.execute("SELECT package_id FROM packages WHERE release_id=? AND release_version=?",
                                         (manifest.release_id, manifest.release_version)).fetchone()
                    if same:
                        ack.update(outcome="ALREADY_IMPORTED", reason_code="SAME_PACKAGE", state="INACTIVE")
                    elif reused:
                        ack.update(outcome="CONFLICT", reason_code="VERSION_CONFLICT")
                    else:
                        con.execute("INSERT INTO packages VALUES (?,?,?,?,?,?,?,?)", (
                            ack["package_id"], manifest.canonical_id, manifest.release_id, manifest.release_version,
                            "INACTIVE", manifest.canonical_json(), canonical(profile.to_dict()), ack["received_at"]))
                        self._insert_files(con, ack["package_id"], files)
                        ack.update(outcome="IMPORTED_INACTIVE", reason_code="VALIDATED_INACTIVE", state="INACTIVE")
                con.execute("INSERT INTO acknowledgements VALUES (?,?)", (ack["ack_id"], canonical(ack)))
            return ack
        except (OSError, sqlite3.Error) as exc:
            raise StorageError("package transaction not acknowledged") from exc

    def get_release(self, package_id):
        with self._connect() as con:
            row = con.execute("SELECT manifest_id,release_id,release_version,state,manifest_json,profile_json,received_at "
                              "FROM packages WHERE package_id=?", (package_id,)).fetchone()
        if row is None:
            return None
        keys = ("manifest_id", "release_id", "release_version", "state", "manifest", "profile", "received_at")
        result = dict(zip(keys, row))
        result["manifest"], result["profile"] = json.loads(row[4]), json.loads(row[5])
        return result

    def read_file(self, package_id, path):
        with self._connect() as con:
            row = con.execute("SELECT body,byte_hash FROM files WHERE package_id=? AND path=?", (package_id, path)).fetchone()
        if row is None:
            return None
        if digest(row[0]) != row[1]:
            raise StorageError("retained byte integrity failure")
        return row[0]

    def get_ack(self, ack_id):
        with self._connect() as con:
            row = con.execute("SELECT body FROM acknowledgements WHERE ack_id=?", (ack_id,)).fetchone()
        return json.loads(row[0]) if row else None
