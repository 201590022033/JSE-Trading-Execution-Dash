"""Read retained direct-issuer SENS/news without implying scheduled events.

The existing anticipatory-radar source archive provides bounded receipt and
publication clocks. This adapter does not collect, write, invoke a model, or
infer that a date in a headline is an event date.
"""
from datetime import datetime, timezone
from urllib.parse import urlsplit

from application.opportunities.public_research import public_share_catalog
from market_intelligence import anticipatory_radar
from market_intelligence.weekly_brief import relevance_check

VERSION = 'issuer-retained-news-v1'


def issuer_news(repo, instrument, product, *, now=None):
    when = now or datetime.now(timezone.utc)
    if not isinstance(when, datetime) or when.tzinfo is None or when.utcoffset() is None:
        raise ValueError('timezone-aware observation time required')
    base = {'schema': VERSION, 'instrument': instrument, 'product': product,
            'observed_at': when.isoformat(), 'items': [], 'research_only': True,
            'live_execution': False,
            'limitations': 'Direct name mention does not verify issuer exposure, publisher authenticity, event date or future occurrence. Retained text is research context, not a recommendation.'}
    if product != 'CASH_SHARE':
        return {**base, 'state': 'UNAVAILABLE', 'reason': 'PRODUCT_UNSUPPORTED'}
    catalog = public_share_catalog()
    if not isinstance(instrument, str) or instrument not in catalog or not catalog[instrument].get('name'):
        return {**base, 'state': 'UNAVAILABLE', 'reason': 'ISSUER_MAPPING_UNAVAILABLE'}
    try:
        sources = anticipatory_radar.sources(repo, when)
    except Exception:
        return {**base, 'state': 'UNAVAILABLE', 'reason': 'RETAINED_SOURCES_UNAVAILABLE'}
    if not isinstance(sources, list):
        return {**base, 'state': 'UNAVAILABLE', 'reason': 'RETAINED_SOURCES_UNAVAILABLE'}
    items, incomplete = [], 0
    for source in sources:
        try:
            if str(source.get('source_id', '')).startswith('calendar-source-'):
                continue  # Calendar citations belong in the scheduled-events view.
            body, url, receipt = source['body'], source['url'], source['available_at']
            if not isinstance(body, str) or not body.strip() or not isinstance(receipt, str):
                raise ValueError('missing source content or receipt')
            stamp = datetime.fromisoformat(receipt.replace('Z', '+00:00'))
            if stamp.tzinfo is None or stamp.utcoffset() is None or stamp > when:
                raise ValueError('unqualified receipt')
            parsed = urlsplit(url)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('invalid source URL')
            match = relevance_check([instrument], [{'evidence_id': source['source_id'],
                                      'headline': '', 'summary': body}], catalog)
            if match['state'] != 'DIRECT_ISSUER_MENTION':
                continue
            # Keep publication and observation separate. The source archive
            # sets published_at only for qualified publication timestamps.
            publication = source.get('published_at')
            if publication:
                published = datetime.fromisoformat(publication.replace('Z', '+00:00'))
                if published.tzinfo is None or published.utcoffset() is None or published > when:
                    raise ValueError('unqualified publication clock')
            provenance = source.get('sens_provenance')
            precision = provenance.get('publication') if isinstance(provenance, dict) else None
            # Preserve older retained items, explicitly distinguishing the
            # existing source-window test from a verified live feed.
            try:
                freshness = 'CURRENT_SOURCE_WINDOW' if anticipatory_radar.news_is_current(source, when) else 'OUTSIDE_SOURCE_WINDOW'
            except (ValueError, TypeError, KeyError, AttributeError):
                freshness = 'UNKNOWN'
            headline = next((line.strip() for line in body.splitlines() if line.strip()), '')[:350]
            items.append({'source_id': source['source_id'], 'receipt_id': source.get('receipt_id'),
                          'headline': headline, 'source_url': url, 'published_at': publication,
                          'publication_detail': precision, 'observed_at': receipt,
                          'issuer_match': 'DIRECT_ISSUER_MENTION',
                          'source_window': freshness,
                          'source_kind': 'RETAINED_SENS' if isinstance(provenance, dict) else 'RETAINED_NEWS_OR_SOURCE',
                          'scheduled_event_date': None})
        except (KeyError, ValueError, TypeError, AttributeError):
            incomplete += 1
    return {**base, 'items': items[:5], 'state': 'PARTIAL' if incomplete else 'AVAILABLE' if items else 'NO_MATCH',
            'reason': 'SOME_SOURCE_RECORDS_UNVERIFIABLE' if incomplete else None,
            'unverifiable_count': incomplete, 'returned_count': min(5, len(items))}
