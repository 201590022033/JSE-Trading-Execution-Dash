"""Bounded transport validation. No app, provider, scorer or engine execution."""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

from jse_intelligence_core import ContractError, EvidenceReference, RadarReleaseManifest, SectorScope
from jse_intelligence_core.contracts import HORIZONS

MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES = 64, 256 * 1024, 2 * 1024 * 1024
MAX_DEPTH, MAX_NODES = 16, 10000


class Rejection(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def checked_hash(value):
    if type(value) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise Rejection("BAD_DIGEST")
    return value


def identifier(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}", value):
        raise Rejection("INVALID_ENVELOPE")
    return value


def exact(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise Rejection("INVALID_ENVELOPE")


def parse_json(raw):
    if len(raw) > MAX_FILE_BYTES:
        raise Rejection("LIMIT_EXCEEDED")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Rejection("INVALID_JSON")
            result[key] = value
        return result
    def invalid(_):
        raise Rejection("INVALID_JSON")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid)
        pending, count = [(value, 0)], 0
        while pending:
            item, depth = pending.pop()
            count += 1
            if count > MAX_NODES or depth > MAX_DEPTH:
                raise Rejection("LIMIT_EXCEEDED")
            if isinstance(item, float) and not math.isfinite(item):
                raise Rejection("INVALID_JSON")
            children = item.values() if type(item) is dict else item if type(item) is list else ()
            if len(children) + count > MAX_NODES:
                raise Rejection("LIMIT_EXCEEDED")
            pending.extend((child, depth + 1) for child in children)
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, Rejection):
            raise
        raise Rejection("INVALID_JSON") from exc


def plain_path(path):
    """Reject links/reparse points in every existing lexical path component."""
    path = Path(os.path.abspath(path))
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise Rejection("UNSAFE_PATH")
    return path


def relative_name(value):
    if type(value) is not str or len(value) > 180 or not 1 <= len(value.split("/")) <= 4:
        raise Rejection("UNSAFE_PATH")
    for part in value.split("/"):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*", part):
            raise Rejection("UNSAFE_PATH")
        if part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(10)], *[f"LPT{i}" for i in range(10)]}:
            raise Rejection("UNSAFE_PATH")
    return value


def read_file(root, name):
    relative_name(name)
    root = plain_path(root)
    path = plain_path(root / name)
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise Rejection("UNSAFE_PATH")
        if before.st_size > MAX_FILE_BYTES:
            raise Rejection("LIMIT_EXCEEDED")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as handle:
            opened = os.fstat(handle.fileno())
            plain_path(path)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino) or opened.st_nlink != 1:
                raise Rejection("SOURCE_CHANGED")
            raw = handle.read(MAX_FILE_BYTES + 1)
            after = os.fstat(handle.fileno())
        if len(raw) > MAX_FILE_BYTES:
            raise Rejection("LIMIT_EXCEEDED")
        if (after.st_size, after.st_mtime_ns) != (opened.st_size, opened.st_mtime_ns):
            raise Rejection("SOURCE_CHANGED")
        return raw
    except FileNotFoundError as exc:
        raise Rejection("MISSING_FILE") from exc
    except OSError as exc:
        raise Rejection("READ_FAILED") from exc


def inventory(root):
    result, pending, visited = [], [plain_path(root)], 0
    try:
        while pending:
            directory = pending.pop()
            for path in directory.iterdir():
                visited += 1
                if visited > MAX_FILES * 2:
                    raise Rejection("LIMIT_EXCEEDED")
                name = path.relative_to(root).as_posix()
                relative_name(name)
                plain_path(path)
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    if len(name.split("/")) >= 4:
                        raise Rejection("LIMIT_EXCEEDED")
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    result.append(name)
                else:
                    raise Rejection("UNSAFE_PATH")
                if len(result) + len(pending) > MAX_FILES:
                    raise Rejection("LIMIT_EXCEEDED")
        return result
    except OSError as exc:
        raise Rejection("READ_FAILED") from exc


@dataclass(frozen=True, slots=True)
class SupportedProfile:
    profile_id: str
    scope: SectorScope
    roles: tuple
    horizons: tuple
    scorer_versions: tuple
    feature_schema_version: str
    model_format_version: str
    runtime_api_version: str
    test_only: bool

    @classmethod
    def from_dict(cls, data):
        exact(data, cls.__dataclass_fields__)
        identifier(data["profile_id"])
        if type(data["test_only"]) is not bool:
            raise Rejection("INVALID_ENVELOPE")
        values = dict(data)
        try:
            values["scope"] = SectorScope.from_dict(data["scope"])
        except (ContractError, OverflowError) as exc:
            raise Rejection("INVALID_CONTRACT") from exc
        for key in ("roles", "horizons", "scorer_versions"):
            items = data[key]
            if type(items) is not list or not items or len(items) > 32 or any(type(i) is not str for i in items) or len(set(items)) != len(items):
                raise Rejection("INVALID_ENVELOPE")
            for item in items:
                identifier(item)
            values[key] = tuple(items)
        if set(values["roles"]) - {"attention", "directional", "policy"} or set(values["horizons"]) - set(HORIZONS):
            raise Rejection("INVALID_ENVELOPE")
        for key in ("feature_schema_version", "model_format_version", "runtime_api_version"):
            identifier(data[key])
        return cls(**values)

    def to_dict(self):
        return {**{key: getattr(self, key) for key in self.__dataclass_fields__},
                "scope": self.scope.to_dict(), "roles": list(self.roles),
                "horizons": list(self.horizons), "scorer_versions": list(self.scorer_versions)}


def load_profiles(path):
    path = plain_path(path)
    data = parse_json(read_file(path.parent, path.name))
    exact(data, ("schema_version", "profiles"))
    if data["schema_version"] != "radar-import-profiles/1":
        raise Rejection("UNSUPPORTED_VERSION")
    if type(data["profiles"]) is not list or len(data["profiles"]) > 64:
        raise Rejection("LIMIT_EXCEEDED")
    profiles = tuple(SupportedProfile.from_dict(p) for p in data["profiles"])
    if len({p.profile_id for p in profiles}) != len(profiles):
        raise Rejection("INVALID_ENVELOPE")
    return profiles


def validate_package(root, profiles, allow_test_profiles, identity):
    root = plain_path(root)
    try:
        marker_raw = read_file(root, "COMPLETE.json")
    except Rejection as exc:
        if exc.code == "MISSING_FILE":
            raise Rejection("INCOMPLETE") from exc
        raise
    marker = parse_json(marker_raw)
    exact(marker, ("schema_version", "envelope_hash"))
    if marker["schema_version"] != "radar-inbox-complete/1":
        raise Rejection("UNSUPPORTED_VERSION")
    envelope_raw = read_file(root, "envelope.json")
    if digest(envelope_raw) != checked_hash(marker["envelope_hash"]):
        raise Rejection("BAD_DIGEST")
    envelope = parse_json(envelope_raw)
    exact(envelope, ("schema_version", "profile_id", "expected_manifest_id", "manifest", "artifacts"))
    if envelope["schema_version"] != "radar-inbox-envelope/1":
        raise Rejection("UNSUPPORTED_VERSION")
    identity.update(package_id=digest(canonical(envelope).encode()),
                    manifest_id=checked_hash(envelope["expected_manifest_id"]),
                    profile_id=identifier(envelope["profile_id"]))
    exact(envelope["manifest"], ("path", "byte_hash"))
    if type(envelope["artifacts"]) is not list or len(envelope["artifacts"]) > MAX_FILES - 3:
        raise Rejection("LIMIT_EXCEEDED")
    files = {"COMPLETE.json": marker_raw, "envelope.json": envelope_raw}
    descriptors, objects = {}, {}
    names = {name.casefold() for name in files}
    def supplied(desc):
        name = relative_name(desc["path"])
        if not name.endswith(".json") or name.casefold() in names:
            raise Rejection("UNSAFE_PATH")
        names.add(name.casefold())
        raw = read_file(root, name)
        if digest(raw) != checked_hash(desc["byte_hash"]):
            raise Rejection("BAD_DIGEST")
        files[name] = raw
        if sum(map(len, files.values())) > MAX_TOTAL_BYTES:
            raise Rejection("LIMIT_EXCEEDED")
        return parse_json(raw)
    manifest_data = supplied(envelope["manifest"])
    if type(manifest_data) is not dict or manifest_data.get("schema_version") != "radar-release-manifest/1":
        raise Rejection("UNSUPPORTED_VERSION")
    try:
        manifest = RadarReleaseManifest.from_dict(manifest_data, expected_id=identity["manifest_id"])
    except (ContractError, OverflowError) as exc:
        raise Rejection("INVALID_CONTRACT") from exc
    identity.update(release_id=manifest.release_id, release_version=manifest.release_version)
    profile = profiles.get(identity["profile_id"])
    if profile is None:
        raise Rejection("UNSUPPORTED_PROFILE")
    identity["test_only"] = profile.test_only
    if profile.test_only and not allow_test_profiles:
        raise Rejection("TEST_PROFILE_DISABLED")
    if profile.scope.canonical_id != manifest.scope.canonical_id:
        raise Rejection("UNSUPPORTED_SCOPE")
    if (manifest.role not in profile.roles or set(manifest.horizons) - set(profile.horizons)
            or manifest.scorer_version not in profile.scorer_versions):
        raise Rejection("UNSUPPORTED_CAPABILITY")
    try:
        manifest.require_compatibility(feature_schema_version=profile.feature_schema_version,
                                       model_format_version=profile.model_format_version,
                                       runtime_api_version=profile.runtime_api_version)
    except ContractError as exc:
        raise Rejection("UNSUPPORTED_CAPABILITY") from exc
    for desc in envelope["artifacts"]:
        exact(desc, ("reference_id", "path", "format", "byte_hash", "canonical_id"))
        rid = identifier(desc["reference_id"])
        if rid in descriptors:
            raise Rejection("REFERENCE_MISMATCH")
        if desc["format"] not in ("json-data/1", "evidence-reference/1"):
            raise Rejection("UNSUPPORTED_FORMAT")
        data = supplied(desc)
        if desc["format"] == "json-data/1":
            exact(data, ("schema_version", "data"))
            if data["schema_version"] != "radar-inert-data/1":
                raise Rejection("UNSUPPORTED_VERSION")
            if desc["canonical_id"] is not None:
                raise Rejection("REFERENCE_MISMATCH")
            objects[rid] = data
        else:
            if type(data) is not dict or data.get("schema_version") != "evidence-reference/1":
                raise Rejection("UNSUPPORTED_VERSION")
            try:
                obj = EvidenceReference.from_dict(data, expected_id=checked_hash(desc["canonical_id"]))
            except (ContractError, OverflowError) as exc:
                raise Rejection("INVALID_CONTRACT") from exc
            if obj.evidence_id != rid:
                raise Rejection("REFERENCE_MISMATCH")
            if datetime.fromisoformat(obj.received_at.replace("Z", "+00:00")) > datetime.fromisoformat(identity["received_at"].replace("Z", "+00:00")):
                raise Rejection("EVIDENCE_LINK")
            objects[rid] = obj
        descriptors[rid] = desc
    used, visiting = set(), set()
    def reference(rid, expected, evidence=False):
        desc = descriptors.get(rid)
        if desc is None or (desc["format"] == "evidence-reference/1") != evidence:
            raise Rejection("REFERENCE_MISMATCH")
        actual = desc["canonical_id"] if evidence else desc["byte_hash"]
        if actual != expected:
            raise Rejection("REFERENCE_MISMATCH")
        if rid in visiting:
            raise Rejection("EVIDENCE_LINK")
        if rid in used:
            return
        used.add(rid)
        if evidence:
            visiting.add(rid)
            obj = objects[rid]
            reference(obj.document_id, obj.content_hash)
            for ref in (obj.source_clock_reference, obj.provenance):
                reference(ref.reference_id, ref.content_hash)
            if obj.original_reference:
                old = obj.original_reference
                reference(old.reference_id, old.content_hash, True)
                original = objects[old.reference_id]
                if (obj.source_id, obj.event_id) != (original.source_id, original.event_id) or any(
                    datetime.fromisoformat(getattr(obj, k).replace("Z", "+00:00")) <
                    datetime.fromisoformat(getattr(original, k).replace("Z", "+00:00"))
                    for k in ("acquired_at", "received_at")
                ):
                    raise Rejection("EVIDENCE_LINK")
            visiting.remove(rid)
    for ref in (*manifest.content_references, manifest.scope.universe, manifest.scope.exposures,
                *manifest.scope.context_references):
        reference(ref.reference_id, ref.content_hash)
    for ref in manifest.evidence_references:
        reference(ref.reference_id, ref.content_hash, True)
    if used != set(descriptors):
        raise Rejection("UNDECLARED_FILE")
    actual_names = inventory(root)
    if set(actual_names) != set(files):
        raise Rejection("UNDECLARED_FILE")
    if read_file(root, "COMPLETE.json") != marker_raw or read_file(root, "envelope.json") != envelope_raw:
        raise Rejection("SOURCE_CHANGED")
    return manifest, profile, files
