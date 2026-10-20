"""Bounded, deterministic frozen JSON evaluation; no provider/model loaders."""
from datetime import date, datetime
import math
import re

from application.release_inbox.protocol import canonical, digest, exact, parse_json, Rejection
from jse_intelligence_core import ContractError, EvidenceReference, RadarReleaseManifest, keyword_score
from jse_intelligence_core.contracts import _instant

FEATURE_VERSION = "radar-text-features/1"
MODEL_VERSION = "radar-linear-json/1"
API_VERSION = "radar-evaluator/1"
SCORER_VERSION = "radar-linear-v1"


class RadarError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise RadarError(code)


def timestamp(value):
    try:
        return datetime.fromisoformat(_instant(value).replace("Z", "+00:00"))
    except (ValueError, OverflowError, TypeError) as exc:
        raise RadarError("INVALID_CLOCK") from exc


def bounded(value):
    try:
        return parse_json(canonical(value).encode())
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise RadarError("INVALID_JSON") from exc


def closed(value, keys):
    try:
        exact(value, keys)
    except Rejection as exc:
        raise RadarError("INVALID_FIELDS") from exc


def number(value):
    require(type(value) in (int, float) and abs(value) <= 1e6 and math.isfinite(value), "INVALID_NUMBER")
    return value


def model_validate(model, role):
    closed(model, ("schema_version", "features", "coefficients", "intercept", "alert_threshold",
                   "max_age_seconds", "weight_origin"))
    require(model["schema_version"] == MODEL_VERSION, "UNSUPPORTED_MODEL")
    require(role in ("attention", "directional"), "POLICY_REQUIRES_STRATEGY_RELEASE")
    require(type(model["features"]) is list and 1 <= len(model["features"]) <= 32, "UNSUPPORTED_FEATURES")
    names = []
    for feature in model["features"]:
        closed(feature, ("name", "kind", "term"))
        require(type(feature["name"]) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", feature["name"]), "UNSUPPORTED_FEATURES")
        require(feature["kind"] in ("legacy_keyword_score", "substring"), "UNSUPPORTED_FEATURES")
        if feature["kind"] == "substring":
            require(type(feature["term"]) is str and 1 <= len(feature["term"].strip()) <= 100
                    and feature["term"] == feature["term"].strip(), "UNSUPPORTED_FEATURES")
        else:
            require(feature["term"] is None, "UNSUPPORTED_FEATURES")
        names.append(feature["name"])
    require(len(set(names)) == len(names), "UNSUPPORTED_FEATURES")
    require(type(model["coefficients"]) is list and len(model["coefficients"]) == len(names), "INVALID_NUMBER")
    for value in (*model["coefficients"], model["intercept"], model["alert_threshold"]):
        number(value)
    require(0 <= model["alert_threshold"] <= 1, "INVALID_NUMBER")
    require(type(model["max_age_seconds"]) is int and 1 <= model["max_age_seconds"] <= 86400, "INVALID_FRESHNESS")
    require(model["weight_origin"] in ("fixed", "research_fitted"), "INVALID_WEIGHT_ORIGIN")
    return model


def compute(model, role, headline, body):
    text = f"{headline} {body}"
    values = {f["name"]: keyword_score(text) if f["kind"] == "legacy_keyword_score"
              else float(f["term"].lower() in text.lower()) for f in model["features"]}
    contributions = {f["name"]: values[f["name"]] * c
                     for f, c in zip(model["features"], model["coefficients"])}
    raw = model["intercept"] + sum(contributions.values())
    score = max(0.0 if role == "attention" else -1.0, min(1.0, raw))
    return dict(score=score, features=values, contributions=contributions,
                direction=None if role == "attention" else (1 if score > 0 else -1 if score < 0 else 0),
                alert=abs(score) >= model["alert_threshold"], policy_input=False, order_intent=None)


def load_release(inbox, package_id, model_id, parity_id):
    record = inbox.get_release(package_id)
    require(record is not None and record["state"] == "INACTIVE", "NOT_IMPORTED")
    manifest = RadarReleaseManifest.from_dict(record["manifest"], expected_id=record["manifest_id"])
    require(manifest.role in ("attention", "directional"), "POLICY_REQUIRES_STRATEGY_RELEASE")
    require(manifest.scorer_version == SCORER_VERSION, "UNSUPPORTED_SCORER")
    try:
        manifest.require_compatibility(feature_schema_version=FEATURE_VERSION,
                                       model_format_version=MODEL_VERSION, runtime_api_version=API_VERSION)
    except ContractError as exc:
        raise RadarError("UNSUPPORTED_CAPABILITY") from exc
    require(all(v.product_type in ("cash_share", "equity_etf") for v in manifest.vehicles), "UNSUPPORTED_PRODUCT")
    envelope = parse_json(inbox.read_file(package_id, "envelope.json"))
    require(digest(canonical(envelope).encode()) == package_id, "PACKAGE_INTEGRITY")
    manifest_raw = inbox.read_file(package_id, envelope["manifest"]["path"])
    require(manifest_raw is not None and digest(manifest_raw) == envelope["manifest"]["byte_hash"]
            and envelope["expected_manifest_id"] == manifest.canonical_id
            and canonical(parse_json(manifest_raw)) == canonical(manifest.to_dict()), "MANIFEST_INTEGRITY")
    refs = {r.reference_id: r.content_hash for r in manifest.content_references}
    def data(rid):
        require(rid in refs, "MISSING_ARTIFACT")
        entries = [d for d in envelope["artifacts"] if d["reference_id"] == rid]
        require(len(entries) == 1 and entries[0]["format"] == "json-data/1", "UNSUPPORTED_FORMAT")
        raw = inbox.read_file(package_id, entries[0]["path"])
        require(raw is not None and digest(raw) == refs[rid], "ARTIFACT_INTEGRITY")
        wrapper = parse_json(raw)
        closed(wrapper, ("schema_version", "data"))
        require(wrapper["schema_version"] == "radar-inert-data/1", "UNSUPPORTED_FORMAT")
        return wrapper["data"], refs[rid]
    model, model_hash = data(model_id)
    parity, parity_hash = data(parity_id)
    model_validate(model, manifest.role)
    closed(parity, ("schema_version", "cases"))
    require(parity["schema_version"] == "radar-parity/1" and type(parity["cases"]) is list
            and 4 <= len(parity["cases"]) <= 64, "INVALID_PARITY")
    ids = set()
    for case in parity["cases"]:
        closed(case, ("case_id", "headline", "text", "expected"))
        require(type(case["case_id"]) is str and case["case_id"] not in ids, "INVALID_PARITY")
        ids.add(case["case_id"])
        require(type(case["headline"]) is str and type(case["text"]) is str, "INVALID_PARITY")
        require(canonical(compute(model, manifest.role, case["headline"], case["text"])) == canonical(case["expected"]), "PARITY_MISMATCH")
    require({"positive", "negative", "neutral", "missing"} <= ids, "INVALID_PARITY")
    return record, manifest, model, model_hash, parity_hash


def validate_snapshot(snapshot):
    snapshot = bounded(snapshot)
    closed(snapshot, ("schema_version", "scope_id", "instrument_id", "product_type", "horizon",
                      "evidence", "document", "source_clock", "provenance"))
    require(snapshot["schema_version"] == "radar-snapshot/1", "UNSUPPORTED_SNAPSHOT")
    try:
        evidence = EvidenceReference.from_dict(snapshot["evidence"])
    except (ValueError, TypeError, OverflowError) as exc:
        raise RadarError("INVALID_EVIDENCE") from exc
    for field in ("scope_id", "instrument_id", "product_type", "horizon"):
        require(type(snapshot[field]) is str and 1 <= len(snapshot[field]) <= 256, "INVALID_FIELDS")
    expected = {"document": evidence.content_hash, "source_clock": evidence.source_clock_reference.content_hash,
                "provenance": evidence.provenance.content_hash}
    objects = {}
    for field, expected_hash in expected.items():
        require(type(snapshot[field]) is str, "INVALID_FIELDS")
        raw = snapshot[field].encode("utf-8")
        require(digest(raw) == expected_hash, "EVIDENCE_BYTES_MISMATCH")
        value = parse_json(raw)
        closed(value, ("schema_version", "data"))
        require(value["schema_version"] == "radar-inert-data/1", "UNSUPPORTED_FORMAT")
        objects[field] = value["data"]
    document = objects["document"]
    closed(document, ("headline", "text"))
    require(all(type(document[k]) is str and len(document[k]) <= 40000 for k in document), "INVALID_FIELDS")
    return snapshot, evidence, document, digest(canonical(snapshot).encode())


def evaluate_current(manifest, model, snapshot, evidence, document, policy, catalog, source_ids, now):
    require(snapshot["scope_id"] == manifest.scope.scope_id, "OUT_OF_SCOPE")
    require((snapshot["instrument_id"], snapshot["product_type"]) in
            {(v.instrument_id, v.product_type) for v in manifest.vehicles}, "OUT_OF_SCOPE")
    require(snapshot["horizon"] in manifest.horizons, "UNSUPPORTED_HORIZON")
    require(all(date.fromisoformat(ref.as_of) <= now.date() for ref in (manifest.scope.universe, manifest.scope.exposures)), "FUTURE_SCOPE")
    require(evidence.source_id in source_ids, "UNSUPPORTED_SOURCE")
    closed(policy, ("source_id", "enabled", "admissible", "observed_at"))
    require(policy["source_id"] == evidence.source_id and policy["enabled"] is True
            and policy["admissible"] is True, "SOURCE_DISABLED_OR_INADMISSIBLE")
    require(0 <= (now - timestamp(policy["observed_at"])).total_seconds() <= 60, "STALE_SOURCE_POLICY")
    require(evidence.revision_kind == "original", "UNSUPPORTED_CORRECTION")
    require(evidence.reconstruction_state == "observed", "UNAVAILABLE_PROVENANCE")
    require(0 <= (now - timestamp(evidence.received_at)).total_seconds() <= model["max_age_seconds"], "STALE_OR_FUTURE_SOURCE")
    require(0 <= (now - timestamp(evidence.acquired_at)).total_seconds() <= model["max_age_seconds"], "STALE_OR_FUTURE_SOURCE")
    if evidence.publication.precision == "exact":
        require(0 <= (now - timestamp(evidence.publication.value)).total_seconds() <= model["max_age_seconds"], "STALE_OR_FUTURE_SOURCE")
    require(snapshot["instrument_id"] in catalog, "UNSUPPORTED_ISSUER")
    issuer = catalog[snapshot["instrument_id"]]
    # Additional necessary check, never a replacement for existing R12 admission.
    require(bool(re.search(r"(?<!\w)" + re.escape(issuer) + r"(?!\w)",
                           document["headline"] + " " + document["text"], re.I)), "NO_DIRECT_ISSUER_MENTION")
    if manifest.role == "directional":
        require(evidence.publication.precision == "exact" and evidence.publication.basis == "source_asserted", "PUBLICATION_TIME_UNAVAILABLE")
    result = compute(model, manifest.role, document["headline"], document["text"])
    return {**result, "publication_precision": evidence.publication.precision,
            "available_at": evidence.received_at, "evidence_id": evidence.evidence_id,
            "evidence_identity": evidence.canonical_id}
