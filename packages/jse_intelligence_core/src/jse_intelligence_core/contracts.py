"""Closed v1 schemas; deterministic JSON identities, without I/O or app imports."""
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime, timezone
import hashlib
import json
import re


class ContractError(ValueError):
    """Input is outside the supported interchange contract."""


def _text(value, name):
    if type(value) is not str or not value or value != value.strip():
        raise ContractError(f"{name}: nonempty trimmed string required")
    if any(ord(c) < 32 for c in value):
        raise ContractError(f"{name}: control characters forbidden")


def _id(value, name):
    _text(value, name)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/+-]*", value):
        raise ContractError(f"{name}: explicit identifier required (no wildcards)")


def _hash(value):
    if type(value) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ContractError("canonical lowercase sha256:<64 hex> required")


def _choice(value, choices, name):
    if type(value) is not str or value not in choices:
        raise ContractError(f"{name}: unsupported value")


def _day(value):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ContractError("ISO calendar date required")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError("invalid calendar date") from exc


def _instant(value):
    # An explicit offset resolves DST folds. RFC3339 -00:00 means unknown offset.
    if type(value) is not str or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:[0-5]\d)", value
    ) or value.endswith("-00:00"):
        raise ContractError("offset-aware RFC3339 instant required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("invalid instant") from exc
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _version(value, expected):
    if type(value) is not str or value != expected:
        raise ContractError(f"expected schema {expected}")


def _tuple(value, kind, name, *, empty=False):
    if type(value) is not tuple or (not empty and not value):
        raise ContractError(f"{name}: {'possibly empty' if empty else 'nonempty'} tuple required")
    if any(type(item) is not kind for item in value):
        raise ContractError(f"{name}: invalid member type")
    if len(set(value)) != len(value):
        raise ContractError(f"{name}: duplicate member")


class _Contract:
    __slots__ = ()

    def to_dict(self):
        """Return a detached JSON-compatible value, never mutable internal state."""
        return json.loads(self.canonical_json())

    def canonical_json(self):
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False)

    @property
    def canonical_id(self):
        return "sha256:" + hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, value, *, expected_id=None):
        if type(value) is not dict or set(value) != {f.name for f in fields(cls)}:
            raise ContractError(f"{cls.__name__}: exact fields required")
        data = dict(value)
        for name, kind in cls._nested.items():
            data[name] = kind.from_dict(data[name])
        for name, kind in cls._arrays.items():
            if type(data[name]) is not list:
                raise ContractError(f"{name}: JSON array required")
            data[name] = tuple(kind.from_dict(v) if kind is not str else v for v in data[name])
        result = cls(**data)
        if expected_id is not None:
            _hash(expected_id)
            if result.canonical_id != expected_id:
                raise ContractError("canonical identity mismatch")
        return result

    @classmethod
    def from_json(cls, value, *, expected_id=None):
        def unique(pairs):
            result = {}
            for key, item in pairs:
                if key in result:
                    raise ContractError("duplicate JSON key")
                result[key] = item
            return result
        try:
            parsed = json.loads(value, object_pairs_hook=unique)
        except (TypeError, ValueError) as exc:
            raise ContractError("invalid JSON") from exc
        return cls.from_dict(parsed, expected_id=expected_id)

    _nested = {}
    _arrays = {}


@dataclass(frozen=True, slots=True, kw_only=True)
class ArtifactReference(_Contract):
    reference_id: str
    content_hash: str

    def __post_init__(self):
        _id(self.reference_id, "reference_id")
        _hash(self.content_hash)


@dataclass(frozen=True, slots=True, kw_only=True)
class DatedReference(_Contract):
    reference_id: str
    content_hash: str
    as_of: str

    def __post_init__(self):
        _id(self.reference_id, "reference_id")
        _hash(self.content_hash)
        _day(self.as_of)


PRODUCT_TYPES = ("cash_share", "equity_etf", "metal_product", "currency_product",
                 "etn", "unit_trust", "synthetic_basket", "cfd", "ssf", "future")


@dataclass(frozen=True, slots=True, kw_only=True)
class InstrumentPermission(_Contract):
    instrument_id: str
    product_type: str

    def __post_init__(self):
        _id(self.instrument_id, "instrument_id")
        _choice(self.product_type, PRODUCT_TYPES, "product_type")


@dataclass(frozen=True, slots=True, kw_only=True)
class SectorScope(_Contract):
    scope_id: str
    group_kind: str
    universe: DatedReference
    exposures: DatedReference
    allowed_instruments: tuple[InstrumentPermission, ...]
    context_references: tuple[ArtifactReference, ...]
    schema_version: str = "sector-scope/1"

    _nested = {"universe": DatedReference, "exposures": DatedReference}
    _arrays = {"allowed_instruments": InstrumentPermission, "context_references": ArtifactReference}

    def __post_init__(self):
        _version(self.schema_version, "sector-scope/1")
        _id(self.scope_id, "scope_id")
        _choice(self.group_kind, ("official_sector", "research_group"), "group_kind")
        if type(self.universe) is not DatedReference or type(self.exposures) is not DatedReference:
            raise ContractError("dated universe and exposure references required")
        _tuple(self.allowed_instruments, InstrumentPermission, "allowed_instruments")
        _tuple(self.context_references, ArtifactReference, "context_references", empty=True)
        ids = [p.instrument_id for p in self.allowed_instruments]
        if len(ids) != len(set(ids)):
            raise ContractError("one explicit product type per instrument required")
        context_ids = [r.reference_id for r in self.context_references]
        if len(context_ids) != len(set(context_ids)) or set(ids) & set(context_ids):
            raise ContractError("context-only and permitted instruments must be disjoint")

    def permits(self, instrument_id, product_type):
        return any(p.instrument_id == instrument_id and p.product_type == product_type
                   for p in self.allowed_instruments)


@dataclass(frozen=True, slots=True, kw_only=True)
class PublicationClock(_Contract):
    value: str | None
    precision: str
    timezone_state: str
    basis: str

    def __post_init__(self):
        _choice(self.precision, ("exact", "date", "unknown"), "precision")
        _choice(self.timezone_state, ("offset_known", "unknown", "ambiguous"), "timezone_state")
        _choice(self.basis, ("source_asserted", "unverified"), "basis")
        if self.precision == "exact":
            if self.timezone_state != "offset_known" or self.basis != "source_asserted":
                raise ContractError("exact publication requires source assertion and resolved offset")
            object.__setattr__(self, "value", _instant(self.value))
        elif self.precision == "date":
            _day(self.value)
            if self.timezone_state == "offset_known":
                raise ContractError("date-only clock cannot assert an exact offset")
        elif self.value is not None or self.timezone_state == "offset_known":
            raise ContractError("unknown clock cannot assert time or resolved offset")


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceReference(_Contract):
    evidence_id: str
    source_id: str
    document_id: str
    event_id: str
    content_hash: str
    publication: PublicationClock
    source_clock_reference: ArtifactReference
    acquired_at: str
    received_at: str
    revision_kind: str
    original_reference: ArtifactReference | None
    reconstruction_state: str
    provenance: ArtifactReference
    schema_version: str = "evidence-reference/1"

    _nested = {"publication": PublicationClock, "source_clock_reference": ArtifactReference,
               "provenance": ArtifactReference}

    @classmethod
    def from_dict(cls, value, *, expected_id=None):
        if type(value) is dict and value.get("original_reference") is not None:
            value = dict(value)
            value["original_reference"] = ArtifactReference.from_dict(value["original_reference"])
        return super(EvidenceReference, cls).from_dict(value, expected_id=expected_id)

    def __post_init__(self):
        _version(self.schema_version, "evidence-reference/1")
        for name in ("evidence_id", "source_id", "document_id", "event_id"):
            _id(getattr(self, name), name)
        _hash(self.content_hash)
        if type(self.publication) is not PublicationClock:
            raise ContractError("publication clock required")
        for name in ("source_clock_reference", "provenance"):
            if type(getattr(self, name)) is not ArtifactReference:
                raise ContractError(f"{name}: artifact reference required")
        for name in ("acquired_at", "received_at"):
            object.__setattr__(self, name, _instant(getattr(self, name)))
        acquired = datetime.fromisoformat(self.acquired_at.replace("Z", "+00:00"))
        received = datetime.fromisoformat(self.received_at.replace("Z", "+00:00"))
        if received < acquired:
            raise ContractError("actual receipt must not precede acquisition")
        if self.publication.precision == "exact":
            published = datetime.fromisoformat(self.publication.value.replace("Z", "+00:00"))
            if published > acquired:
                raise ContractError("published exact time must not follow actual acquisition")
        _choice(self.revision_kind, ("original", "correction"), "revision_kind")
        if self.revision_kind == "original":
            if self.original_reference is not None:
                raise ContractError("original cannot claim correction linkage")
        elif type(self.original_reference) is not ArtifactReference or self.original_reference.reference_id == self.evidence_id:
            raise ContractError("correction requires a distinct original reference")
        _choice(self.reconstruction_state, ("observed", "reconstructed", "unverified"), "reconstruction_state")


HORIZONS = ("next_5m", "open_15m", "open_20m", "open_30m", "sessions_2", "sessions_3",
            "sessions_4", "sessions_5", "weekly", "long_term")


@dataclass(frozen=True, slots=True, kw_only=True)
class RadarReleaseManifest(_Contract):
    release_id: str
    release_version: str
    scorer_version: str
    scope: SectorScope
    vehicles: tuple[InstrumentPermission, ...]
    horizons: tuple[str, ...]
    role: str
    content_references: tuple[ArtifactReference, ...]
    evidence_references: tuple[ArtifactReference, ...]
    feature_schema_version: str
    model_format_version: str
    runtime_api_version: str
    schema_version: str = "radar-release-manifest/1"

    _nested = {"scope": SectorScope}
    _arrays = {"vehicles": InstrumentPermission, "horizons": str,
               "content_references": ArtifactReference, "evidence_references": ArtifactReference}

    def __post_init__(self):
        _version(self.schema_version, "radar-release-manifest/1")
        for name in ("release_id", "release_version", "scorer_version", "feature_schema_version",
                     "model_format_version", "runtime_api_version"):
            _id(getattr(self, name), name)
        if type(self.scope) is not SectorScope:
            raise ContractError("explicit sector scope required")
        _tuple(self.vehicles, InstrumentPermission, "vehicles")
        if any(not self.scope.permits(p.instrument_id, p.product_type) for p in self.vehicles):
            raise ContractError("release vehicles must be within permitted trading scope")
        _tuple(self.horizons, str, "horizons")
        for horizon in self.horizons:
            _choice(horizon, HORIZONS, "horizon")
        _choice(self.role, ("attention", "directional", "policy"), "role")
        for name in ("content_references", "evidence_references"):
            refs = getattr(self, name)
            _tuple(refs, ArtifactReference, name)
            if len({r.reference_id for r in refs}) != len(refs):
                raise ContractError(f"{name}: conflicting reference identities")

    def require_compatibility(self, *, feature_schema_version, model_format_version, runtime_api_version):
        """Exact capability comparison only; never activates, loads, or executes artifacts."""
        if (feature_schema_version, model_format_version, runtime_api_version) != (
            self.feature_schema_version, self.model_format_version, self.runtime_api_version
        ):
            raise ContractError("unsupported feature/model/runtime compatibility")
