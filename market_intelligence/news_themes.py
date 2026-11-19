"""Bounded, read-only topic and issuer relevance over retained source receipts."""
from collections import Counter
from datetime import date, datetime, time, timedelta
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from .anticipatory_radar import sources
from .weekly_brief import relevance_check

SAST = ZoneInfo('Africa/Johannesburg')
MAX_ITEMS = 2000

# Terms are reviewable topic concepts. Each entry can be extended independently
# without changing issuer matching, source acquisition or model budgets.
VOCABULARY = {
    'monetary_policy': ('Monetary policy', r'\b(?:SARB|MPC|reserve bank|monetary policy|repo rates?|interest[- ]rate (?:cuts?|hikes?|decisions?|verdicts?))\b'),
    'rand_exchange': ('Rand and exchange rates', r'\b(?:rand\s+(?:weakens?|strengthens?|firms?|slips?|gains?|falls?|rises?|trades?|exchange rate)|(?:stronger|weaker|South African)\s+rand|USD\s*[/\-]\s*ZAR|ZAR\s*[/\-]\s*USD)\b'),
    'inflation': ('Inflation', r'\b(?:inflation|CPI|consumer prices?)\b'),
    'ownership_transactions': ('Ownership transactions', r'\b(?:acquisitions?|mergers?|takeovers?|share sales?|transactions?|disposals?)\b'),
    'telecom_infrastructure': ('Telecom infrastructure', r'\b(?:telecom(?:munications)?|(?:mobile|cell) towers?|tower companies|fibre networks?|5G)\b'),
    'energy_supply': ('Energy supply', r'\b(?:load.shedding|electricity supply|power generation|crude oil|Brent)\b'),
}
PATTERNS = {key: re.compile(pattern, re.I) for key, (_, pattern) in VOCABULARY.items()}


def _url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('public source URL required')
    query = sorted((key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True)
                   if not key.lower().startswith('utm_') and key.lower() not in ('fbclid', 'gclid'))
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip('/'), urlencode(query), ''))


def _unique_sources(retained, start, end):
    by_url = {}
    invalid = 0
    for source in retained:
        try:
            if source['source_id'].startswith('calendar-source-'):
                continue
            when = datetime.fromisoformat(source['available_at'])
            if when.tzinfo is None:
                raise ValueError('receipt timezone required')
            if not start <= when <= end:
                continue
            headline = source['body'].splitlines()[0].strip()
            if not headline:
                raise ValueError('headline required')
            url = _url(source['url'])
            prior = by_url.get(url)
            if prior is None or (when, source['source_id']) < (prior[0], prior[1]['source_id']):
                by_url[url] = (when, source, headline)
        except (KeyError, ValueError, TypeError, IndexError, AttributeError):
            invalid += 1
    unique = {}
    for when, source, headline in sorted(by_url.values(), key=lambda item: (item[0], item[1]['source_id'])):
        normalized = ' '.join(re.findall(r'\w+', headline.casefold()))
        key = normalized if len(normalized) >= 30 else source['source_id']
        unique.setdefault(key, (when, source, headline))
    return list(unique.values()), len(by_url), invalid


def summarize(repo, now, *, instrument=None, end_day=None):
    from application.opportunities.public_research import public_share_catalog
    catalog = public_share_catalog()
    if instrument is not None and (instrument not in catalog or not catalog[instrument].get('name')):
        raise ValueError('Unknown issuer')
    day = date.fromisoformat(end_day) if end_day else now.astimezone(SAST).date()
    end = min(now, datetime.combine(day + timedelta(days=1), time.min, SAST) - timedelta(microseconds=1))
    start = datetime.combine(day - timedelta(days=13), time.min, SAST)
    split = start + timedelta(days=7)
    if day > now.astimezone(SAST).date():
        raise ValueError('Future receipt days are unavailable')
    retained = sources(repo, end, earliest=start)
    unique, url_count, invalid = _unique_sources(retained, start, end)
    rows = {key: {'id': key, 'label': label, 'previous': 0, 'recent': 0,
                  'issuer_previous': 0, 'issuer_recent': 0, 'sources': {}}
            for key, (label, _) in VOCABULARY.items()}
    totals = Counter()
    evidence = {key: [] for key in rows}
    for when, source, headline in reversed(unique[-MAX_ITEMS:]):
        period = 'recent' if when >= split else 'previous'
        totals[period] += 1
        matched = {key: pattern.search(source['body']) for key, pattern in PATTERNS.items()}
        if not any(matched.values()):
            continue
        issuer = instrument is not None and relevance_check([instrument], [{
            'evidence_id': source['source_id'], 'headline': headline, 'summary': source['body']
        }], catalog)['state'] == 'DIRECT_ISSUER_MENTION'
        kind = 'SENS' if source.get('sens_provenance') else 'Retained news or source'
        for key, match in matched.items():
            if match is None:
                continue
            row = rows[key]
            row[period] += 1
            row['issuer_' + period] += int(issuer)
            row['sources'][kind] = row['sources'].get(kind, 0) + 1
            examples = evidence[key]
            item = {'source_id': source['source_id'], 'receipt_id': source.get('receipt_id'),
                    'url': source['url'], 'headline': headline, 'received_at': source['available_at'],
                    'published_at': source.get('published_at'), 'kind': kind, 'term': match.group(),
                    'issuer_mentioned': issuer, 'period': period}
            if len(examples) < 4 or issuer:
                examples.append(item)
                examples.sort(key=lambda x: x['issuer_mentioned'], reverse=True)
                del examples[4:]
    coverage = dict(getattr(retained, 'coverage', {}))
    return {'schema': 'retained-news-themes-v1', 'instrument': instrument,
            'window': {'start': start.date().isoformat(), 'recent_start': split.date().isoformat(),
                       'end': day.isoformat(), 'cutoff': end.isoformat(),
                       'partial_end_day': end == now},
            'coverage': {**coverage, 'retained_rows': len(retained), 'distinct_urls': url_count,
                         'distinct_stories': len(unique), 'invalid_rows': invalid,
                         'analysis_truncated': len(unique) > MAX_ITEMS,
                         'previous_analyzed': totals['previous'], 'recent_analyzed': totals['recent']},
            'themes': [{**row, 'evidence': evidence[key]} for key, row in rows.items()],
            'model_calls_on_read': 0, 'research_only': True}
