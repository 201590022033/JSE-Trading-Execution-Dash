"""Pure port of the legacy per-item heuristic and supplied-assessment normalizer.

This preserves parsing quirks; it establishes neither issuer applicability nor
predictive calibration. It performs no acquisition, inference, or activation.
"""
from dataclasses import asdict, dataclass
import hashlib
import json

from .contracts import ContractError
from ._legacy_news_tables import (
    MACRO_KEYWORDS, TICKER_ALIASES, _BULLISH, _BEARISH, _LLM_TICKER_MAP,
)

SCORER_VERSION = "legacy-news-v1"
SOURCE_REVISION = "6a23b027074ba0cf10004f36f3140723e6319d66"
SOURCE_PATH = "sentiment_analyzer.py"


@dataclass(frozen=True, slots=True)
class ScoredAsset:
    name: str
    direction: int
    strength: float


@dataclass(frozen=True, slots=True)
class ScoringProvenance:
    scorer_version: str
    source_revision: str
    source_path: str
    input_hash: str
    score_origin: str
    asset_origin: str
    analysis_provider: str | None
    analysis_model: str | None
    learned_weights: bool = False


@dataclass(frozen=True, slots=True)
class NewsScore:
    summary: str
    sentiment: str
    score: float
    assets: tuple[ScoredAsset, ...]
    llm_used: bool
    provenance: ScoringProvenance

    def legacy_fields(self):
        """Detached score fields for comparison with AnalyzedItem (no clocks/I/O)."""
        return {
            "summary": self.summary, "sentiment": self.sentiment, "score": self.score,
            "assets": [asdict(asset) for asset in self.assets], "llm_used": self.llm_used,
            "analysis_provider": self.provenance.analysis_provider,
            "analysis_model": self.provenance.analysis_model,
        }

    def to_dict(self):
        return {**self.legacy_fields(), "provenance": asdict(self.provenance)}


def detect_mentions(text: str) -> tuple[ScoredAsset, ...]:
    """Legacy ordered substring mentions, not validated economic exposures."""
    if type(text) is not str:
        raise ContractError("mention text must be a string")
    low = f" {text.lower()} "
    impacts = []
    for asset, keywords in MACRO_KEYWORDS.items():
        if any(k in low for k in keywords):
            impacts.append(ScoredAsset(asset, 0, 0.4))
    for ticker, aliases in TICKER_ALIASES.items():
        if any(a in low for a in aliases):
            impacts.append(ScoredAsset(ticker, 0, 0.5))
    return tuple(impacts)


def keyword_score(text: str) -> float:
    """One vote per matching lexicon entry, with the exact legacy rounding."""
    if type(text) is not str:
        raise ContractError("scoring text must be a string")
    low = text.lower()
    bull = sum(1 for word in _BULLISH if word in low)
    bear = sum(1 for word in _BEARISH if word in low)
    if bull == bear:
        return 0.0
    return round((bull - bear) / (bull + bear), 2)


def score_news(headline: str, text: str | None = "", *, assessment: dict | None = None,
               prior_sentiment: str = "neutral") -> NewsScore:
    """Score supplied text or normalize an already supplied finite JSON assessment.

    None/empty assessment reproduces unavailable-model fallback. A nonempty
    assessment denotes caller-supplied output, never a provider call. The caller
    owns upstream response validation and source/issuer/evidence admission.
    Provenance labels are assertions, not authenticated provider credentials.
    """
    if type(headline) is not str or (text is not None and type(text) is not str):
        raise ContractError("headline and optional body must be strings")
    if type(prior_sentiment) is not str or prior_sentiment not in ("bullish", "bearish", "neutral"):
        raise ContractError("unsupported prior sentiment")
    if assessment is not None and type(assessment) is not dict:
        raise ContractError("assessment must be a JSON object or None")
    if assessment:
        if assessment.get("assets") is not None and type(assessment.get("assets")) is not list:
            raise ContractError("assessment assets must be a JSON array or null")
        if any(type(a) is not dict for a in assessment.get("assets", []) or []):
            raise ContractError("assessment assets must contain objects")
        for key in ("_provider", "_model"):
            if assessment.get(key) is not None and type(assessment[key]) is not str:
                raise ContractError("provider/model labels must be strings or null")
    body = text or ""
    try:
        packet = json.dumps({"headline": headline, "text": body, "assessment": assessment,
                             "prior_sentiment": prior_sentiment},
                            sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ContractError("finite JSON-compatible input required") from exc
    input_hash = "sha256:" + hashlib.sha256(packet.encode("utf-8")).hexdigest()
    # Score the same detached snapshot that the provenance hash binds.
    assessment = json.loads(packet)["assessment"]
    combined = f"{headline} {body}"
    if assessment:
        # Preserve analyze_item's deterministic normalization, including duplicate
        # and unknown names. Provider validity/admission is a separate boundary.
        summary = str(assessment.get("summary") or headline)[:200]
        sentiment = str(assessment.get("sentiment") or prior_sentiment).lower()
        try:
            score = max(-1.0, min(1.0, float(assessment.get("score", 0.0))))
        except (TypeError, ValueError):
            score = 0.0
        impacts = []
        for asset in assessment.get("assets", []) or []:
            try:
                name = str(asset.get("name", "")).upper().strip()
                name = _LLM_TICKER_MAP.get(name, name)
                direction = int(asset.get("direction", 0))
                direction = 1 if direction > 0 else (-1 if direction < 0 else 0)
                strength = max(0.0, min(1.0, float(asset.get("strength", 0.5))))
                if name:
                    impacts.append(ScoredAsset(name, direction, strength))
            except (TypeError, ValueError):
                continue
        provider, model = assessment.get("_provider", "unknown"), assessment.get("_model")
        score_origin, asset_origin = "provider_assessed", "provider_assessed_with_fixed_aliases"
        llm_used = True
    else:
        score = keyword_score(combined)
        direction = 1 if score > 0.1 else (-1 if score < -0.1 else 0)
        impacts = [ScoredAsset(imp.name, direction, min(0.9, abs(score) + 0.2))
                   for imp in detect_mentions(combined)]
        sentiment = "bullish" if score > 0.1 else ("bearish" if score < -0.1 else "neutral")
        summary, provider, model = headline, "keywords", None
        score_origin, asset_origin = "fixed_keyword_heuristic", "fixed_substring_heuristic"
        llm_used = False
    return NewsScore(summary, sentiment, score, tuple(impacts), llm_used,
                     ScoringProvenance(SCORER_VERSION, SOURCE_REVISION, SOURCE_PATH,
                                       input_hash, score_origin, asset_origin, provider, model))
