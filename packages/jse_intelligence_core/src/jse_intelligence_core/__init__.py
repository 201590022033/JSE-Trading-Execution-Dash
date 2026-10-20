"""Pure contracts and versioned legacy scoring; importing activates nothing."""
from .contracts import (
    ArtifactReference, ContractError, DatedReference, EvidenceReference,
    InstrumentPermission, PublicationClock, RadarReleaseManifest, SectorScope,
)

from .legacy_news import (
    NewsScore, ScoredAsset, ScoringProvenance, detect_mentions, keyword_score, score_news,
)

__version__ = "0.2.0"
__all__ = [
    "ArtifactReference", "ContractError", "DatedReference", "EvidenceReference",
    "InstrumentPermission", "PublicationClock", "RadarReleaseManifest", "SectorScope",
    "NewsScore", "ScoredAsset", "ScoringProvenance", "detect_mentions", "keyword_score", "score_news",
]
