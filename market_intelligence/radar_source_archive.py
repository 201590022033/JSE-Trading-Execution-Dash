"""Read-only access to retained Radar source receipts and their history."""
import re
from urllib.parse import urlsplit

from . import research_calendar as calendar
from .anticipatory_radar import ACCOUNT as RADAR_ACCOUNT, VERSION as RADAR_VERSION
from .hermes import ACCOUNT as HERMES_ACCOUNT

_HASH = re.compile(r'^[0-9a-f]{64}$')
_SENS_ID = re.compile(r'^radar-sens-source-[0-9a-f]{64}$')
_CALENDAR_ID = re.compile(r'^calendar-source-[0-9a-f]{64}$')
_HERMES_ID = re.compile(r'^hermes-news-input-[0-9a-f]{64}$')
_RECEIPT_LIMIT = 500


def _visible(record, now):
    return bool(record and record.get('received_at') and
                calendar._at(record['received_at']) <= calendar._at(now))


def _provider(url):
    try:
        return urlsplit(url).hostname
    except (TypeError, ValueError):
        return None


def _document(source_id, receipt_id, body, url, available_at, published_at,
              kind, provider=None, provenance=None, receipt_at=None):
    return {'source_id': source_id, 'source_receipt_id': receipt_id,
            'body': body, 'headline': body.splitlines()[0] if body else '',
            'source_url': url, 'available_at': available_at,
            'published_at': published_at, 'receipt_at': receipt_at or available_at, 'source_kind': kind,
            'provider': provider or _provider(url), 'provenance': provenance,
            'model_calls_on_read': 0}


def _article(capture, article, now):
    if (not isinstance(article, dict) or
            not all(isinstance(article.get(key), str) for key in ('headline', 'summary', 'url', 'received_at'))):
        return None
    published = article.get('timestamp') if article.get('timestamp_kind') == 'published' else None
    try:
        available = max(calendar._at(capture['received_at']), calendar._at(article['received_at']))
    except (TypeError, ValueError):
        return None
    if available > calendar._at(now):
        return None
    body = article['headline'] + '\n' + article['summary']
    source_id = calendar._hash([article['url'], body, published])
    return _document(source_id, capture['capture_id'], body, article['url'],
                     available.isoformat(), published, 'NEWS_HEADLINE_OR_EXCERPT',
                     provider=article.get('publisher'), receipt_at=capture['received_at'])


def _saved_source(record, source_id, now):
    if not _visible(record, now) or record.get('record_id') != source_id:
        return None
    if not isinstance(record.get('body'), str) or not isinstance(record.get('source_url'), str):
        return None
    if _SENS_ID.fullmatch(source_id) and record.get('schema') == RADAR_VERSION:
        return _document(source_id, source_id, record['body'], record['source_url'],
                         record['received_at'], record.get('published_at'),
                         'SENS_HEADLINE', provenance=record.get('sens_provenance'))
    if _CALENDAR_ID.fullmatch(source_id) and record.get('schema') == calendar.VERSION:
        return _document(source_id, source_id, record['body'], record['source_url'],
                         record['received_at'], record.get('published_at'),
                         'CALENDAR_SOURCE', provenance={'captured_at': record.get('captured_at'),
                             'body_sha256': record.get('body_sha256'),
                             'provenance': record.get('provenance')})
    return None


def detail(repo, source_id, now, receipt_id=None):
    """Return the exact retained source body by stable identity, including old receipts.

    Hermes identities represent individual articles inside a capture. Supplying
    its capture ID avoids treating an unrelated record as a source and preserves
    the actual snapshot/receipt clock. No new source is fetched or model called.
    """
    if not isinstance(source_id, str):
        raise ValueError('Source identity required')
    now = calendar._at(now)
    if _SENS_ID.fullmatch(source_id) or _CALENDAR_ID.fullmatch(source_id):
        if receipt_id and receipt_id != source_id:
            raise ValueError('Source receipt identity mismatch')
        document = _saved_source(repo.paper_record(source_id), source_id, now)
        if document:
            return document
    elif _HASH.fullmatch(source_id) and isinstance(receipt_id, str) and _HERMES_ID.fullmatch(receipt_id):
        capture = repo.paper_record(receipt_id)
        if _visible(capture, now) and capture.get('capture_id') == receipt_id:
            for article in capture.get('articles', []):
                document = _article(capture, article, now)
                if document and document['source_id'] == source_id:
                    return document
    raise ValueError('Retained source unavailable at the requested time')


def history(repo, now, *, limit=100, before=None):
    """List a bounded recent receipt window, including no-longer-current sources."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError('History limit must be between 1 and 200')
    now = calendar._at(now)
    before_key = None
    if before is not None:
        if (not isinstance(before, dict) or set(before) not in (
                {'available_at', 'source_id', 'source_receipt_id'},
                {'available_at', 'receipt_at', 'source_id', 'source_receipt_id'})
                or not all(isinstance(value, str) and 0 < len(value) <= 160 for value in before.values())):
            raise ValueError('Valid history cursor required')
        before_at = calendar._at(before.get('receipt_at', before['available_at']))
        if before_at > now:
            raise ValueError('Future history cursor is not allowed')
        before_key = (before_at.isoformat(), before['source_receipt_id'], before['source_id'])
    as_of = before_key[0] if before_key else now.isoformat()
    feeds = ((RADAR_ACCOUNT, 'radar-sens-source'),
             (calendar.ACCOUNT, calendar.KINDS['source']),
             (HERMES_ACCOUNT, 'hermes-news-input'))
    records = [repo.paper_records(account, kind, as_of=as_of, limit=_RECEIPT_LIMIT + 1,
                                  before_record_id=before_key[1] if before_key else None)
               for account, kind in feeds]
    found = {}
    for group in records[:2]:
        for record in group[:_RECEIPT_LIMIT]:
            document = _saved_source(record, record.get('record_id', ''), now)
            if document:
                found[(document['source_id'], document['source_receipt_id'])] = document
    for capture in records[2][:_RECEIPT_LIMIT]:
        if not _visible(capture, now):
            continue
        for article in capture.get('articles', []):
            document = _article(capture, article, now)
            if document:
                found[(document['source_id'], document['source_receipt_id'])] = document
    def identity(item):
        return (calendar._at(item['receipt_at']).isoformat(), item['source_receipt_id'], item['source_id'])
    def receipt_id(row):
        return row.get('record_id') or row.get('capture_id')
    boundaries = [group[_RECEIPT_LIMIT - 1] for group in records
                  if len(group) > _RECEIPT_LIMIT and group[_RECEIPT_LIMIT - 1].get('received_at')
                  and receipt_id(group[_RECEIPT_LIMIT - 1])]
    cutoff = max(((calendar._at(row['received_at']).isoformat(), receipt_id(row), '')
                  for row in boundaries), default=None)
    ordered = sorted((item for item in found.values() if before_key is None or identity(item) < before_key),
                     key=identity, reverse=True)
    if cutoff:
        ordered = [item for item in ordered if identity(item) >= cutoff]
    previews = [{**{k: item[k] for k in ('source_id', 'source_receipt_id', 'headline',
                 'source_url', 'available_at', 'receipt_at', 'published_at', 'source_kind', 'provider')},
                 'excerpt': item['body'][:300]} for item in ordered[:limit]]
    truncated = any(len(group) > _RECEIPT_LIMIT for group in records)
    more = len(ordered) > limit or truncated
    next_cursor = ({k: previews[-1][k] for k in ('available_at', 'receipt_at', 'source_id', 'source_receipt_id')}
                   if previews and more else None)
    if not previews and truncated:
        # Advance past a bounded window containing no usable documents rather
        # than leaving later retained receipts unreachable.
        if boundaries:
            boundary = max(boundaries, key=lambda row: (calendar._at(row['received_at']), receipt_id(row)))
            next_cursor = {'available_at': boundary['received_at'], 'receipt_at': boundary['received_at'],
                           'source_receipt_id': receipt_id(boundary), 'source_id': '!'}
    return {'sources': previews, 'limit': limit, 'next_cursor': next_cursor,
            'more_available': more, 'receipt_window_truncated': truncated,
            'scope': 'BOUNDED_RETAINED_RECEIPTS', 'model_calls_on_read': 0}
