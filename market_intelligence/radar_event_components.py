"""Source-fragment event watches and independently sourced date-only timelines.

All records are append-only. A split is a host text suggestion, a date link is
an attributed candidate, and neither implies an occurrence or a trading signal.
"""
from datetime import date, datetime, time, timedelta, timezone
import re
from zoneinfo import ZoneInfo

from . import anticipatory_radar as radar, research_calendar as cal

VERSION = 'event-components-v1'
UNKNOWN_ZONE = 'Etc/GMT+12'  # Last civil date to end worldwide; not an event time.
_EVENT = (r'(?:interest[-\s]*)?rate\s+(?:calls?|decisions?)|votes?|voting|elections?|midterms?|results?|earnings|decisions?|meetings?|'
          r'releases?|announcements?|hearings?|summits?|speeches?|reports?|'
          r'dividends?|budgets?|cpi')
_EVENT_RE = re.compile(r'\b(?:' + _EVENT + r')\b', re.I)
_SUBJECT = r"[A-Z][A-Za-z0-9.'-]*(?:\s+[A-Z][A-Za-z0-9.'-]*){0,2}"
_SHARED = re.compile(r'(?P<subjects>' + _SUBJECT + r'(?:\s*(?:,|&|(?i:\band\b))\s*'
                     + _SUBJECT + r'){1,3})\s+(?P<event>(?i:' + _EVENT + r'))\b')
_DATE = re.compile(r'(?<!\w)(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]{3,9},?\s+\d{4}|'
                   r'[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})(?!\w)')
_STOP = {'a', 'an', 'and', 'the', 'for', 'with', 'will', 'from', 'that', 'this',
         'after', 'before', 'about', 'says', 'on', 'at', 'in', 'of', 'to', 'is',
         'are', 'was', 'its', 'scheduled', 'due', 'hold', 'held', 'upcoming',
         'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
         'september', 'october', 'november', 'december', 'jan', 'feb', 'mar',
         'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
         'prepare', 'prepares', 'preparing', 'ahead', 'expects', 'plans', 'intends'}


def date_mentions(text):
    """Return fully specified literal dates, including month-first forms."""
    result = []
    for match in _DATE.finditer(text):
        value = match.group(0)
        parsed = None
        for fmt in ('%Y-%m-%d', '%d %B %Y', '%d %b %Y', '%B %d %Y', '%b %d %Y'):
            try:
                parsed = datetime.strptime(value.replace(',', ''), fmt).date()
                break
            except ValueError:
                pass
        if parsed and parsed < date.max:
            result.append((value, parsed))
    return result


def date_end(day, zone=UNKNOWN_ZONE):
    """Exclusive end of the stated civil date, not a release-time prediction."""
    if isinstance(day, str):
        day = date.fromisoformat(day)
    if day == date.max:
        raise ValueError('Event date needs a representable following day')
    return datetime.combine(day + timedelta(days=1), time.min, ZoneInfo(zone)).astimezone(timezone.utc)


def date_start(day, zone=UNKNOWN_ZONE):
    if isinstance(day, str):
        day = date.fromisoformat(day)
    return datetime.combine(day, time.min, ZoneInfo(zone)).astimezone(timezone.utc)


def _watch(repo, watch_id, now):
    watch = repo.paper_record(watch_id)
    if (not watch or not watch_id.startswith('radar-watch-') or watch.get('schema') != radar.VERSION
            or not {'discovery_id', 'frozen_at', 'date_state', 'kind'} <= watch.keys()
            or cal._at(watch['received_at']) > cal._at(now)):
        raise ValueError('Existing watch available at the review time required')
    return watch


def _components(text):
    """Split recognizable parallel clauses or subjects with a shared event noun."""
    pieces = [p.strip() for p in re.split(r'\s+(?i:and)\s+|\s*;\s*|,\s+(?=[A-Za-z])', text)]
    if 2 <= len(pieces) <= 4 and all(_EVENT_RE.search(p) for p in pieces):
        return [{'label': p, 'fragments': [p], 'dated_fragment': p} for p in pieces]
    match = _SHARED.search(text)
    if not match:
        return []
    subjects = [s.strip() for s in re.split(r'\s*,\s*|\s+and\s+|\s*&\s*', match['subjects'], flags=re.I)]
    if len(subjects) < 2 or len(set(s.lower() for s in subjects)) != len(subjects):
        return []
    return [{'label': s + ' ' + match['event'], 'fragments': [s, match['event']],
             'dated_fragment': None} for s in subjects]


def components_for(watch):
    """Use exact model phrase first; fall back to overlapping headline text."""
    prefix = 'Source mentions: '
    phrase = watch.get('reason', '').removeprefix(prefix).strip()
    quote = watch.get('quote', '')
    if not watch.get('reason', '').startswith(prefix) or not phrase or phrase not in quote:
        return []
    parts = _components(phrase)
    if parts:
        return parts
    headline = quote.splitlines()[0] if quote else ''
    # If Qwen copied only one of several named clauses, split the headline
    # when that precise, non-generic phrase overlaps one of them.
    if len(phrase) >= 4 and not _EVENT_RE.fullmatch(phrase):
        headline_parts = _components(headline)
        if (headline_parts and (_SHARED.search(headline) or _EVENT_RE.search(phrase))
                and any(phrase.lower() in p['label'].lower() for p in headline_parts)):
            for part in headline_parts:
                if phrase.lower() in part['label'].lower() and not _SHARED.search(headline):
                    # Avoid carrying unrelated introductory market commentary
                    # into the event identifier; preserve a complete dated clause.
                    if not date_mentions(part['label']):
                        part.update(label=phrase, fragments=[phrase], dated_fragment=phrase)
            return headline_parts
    match = _SHARED.search(headline)
    # Do not split a different subject merely because the headline contains it.
    if match and len(phrase) >= 4 and not _EVENT_RE.fullmatch(phrase) and (
            phrase.lower() in match.group(0).lower() or match.group(0).lower() in phrase.lower()):
        return _components(match.group(0))
    return []


def _original_source(repo, watch):
    parent = repo.paper_record(watch.get('parent_watch_id')) or watch
    discovery = repo.paper_record(parent.get('discovery_id'))
    packet = repo.paper_record(discovery.get('input_id')) if discovery else None
    return next((s for s in (packet or {}).get('sources', []) if s['source_id'] == parent['source_id']), None)


def _source(repo, watch, source_id, now):
    original = _original_source(repo, watch)
    if original and source_id == original['source_id']:
        source = original
        return {'source_id': source_id, 'url': source['url'], 'body': source['body'],
                'published_at': source.get('published_at'), 'captured_at': source.get('captured_at'),
                'available_at': source['available_at'], 'receipt_id': source['receipt_id']}
    if source_id.startswith('calendar-source-'):
        source = cal._source(repo, source_id, now)
        return {'source_id': source_id, 'url': source['source_url'], 'body': source['body'],
                'published_at': source.get('published_at'), 'captured_at': source['captured_at'],
                'available_at': source['received_at'], 'receipt_id': source['record_id']}
    source = next((s for s in radar.sources(repo, now) if s['source_id'] == source_id), None)
    if not source:
        raise ValueError('Available retained source required')
    return {'source_id': source_id, 'url': source['url'], 'body': source['body'],
            'published_at': source.get('published_at'), 'captured_at': source.get('captured_at'),
            'available_at': source['available_at'], 'receipt_id': source['receipt_id']}


def timings(repo, watch_id, now):
    return sorted((t for t in radar.rows(repo, 'watch-timing', now) if t['watch_id'] == watch_id),
                  key=lambda t: (t['received_at'], t['record_id']))


@cal._write
def record_timing(repo, watch_id, event_date, timezone_name, citations, date_source_id,
                  date_text, explanation, now, *, basis='EXPLICIT_FULL_DATE',
                  origin='ASSISTANT_REVIEWED_SOURCE_DATE'):
    """Bind a literal date, or publication-day 'today', to one event watch.

    Semantic association is an attributed review/candidate; it is not proof of
    occurrence. Its actual record time controls when it affects the watch.
    """
    now = cal._at(now)
    watch = _watch(repo, watch_id, now)
    if any(w.get('parent_watch_id') == watch_id for w in radar.rows(repo, 'watch', now)):
        raise ValueError('Review dates on individual event watches, not their combined parent')
    if not watch.get('reason', '').startswith('Source mentions: '):
        raise ValueError('An individual source event watch is required')
    day = date.fromisoformat(event_date)
    zone = ZoneInfo(timezone_name)
    if not isinstance(citations, list) or not 1 <= len(citations) <= 5:
        raise ValueError('Bounded exact citations required')
    if origin not in {'ASSISTANT_REVIEWED_SOURCE_DATE', 'LOCAL_OPERATOR_SOURCE_DATE_REVIEW', 'HOST_LITERAL_DATE_CANDIDATE'}:
        raise ValueError('Attributed date origin required')
    if not isinstance(date_text, str) or not date_text:
        raise ValueError('Literal date text required')
    verified, date_source, date_quote = [], None, None
    for c in citations:
        if not isinstance(c, dict) or set(c) != {'source_id', 'quote'}:
            raise ValueError('Exact source reference required')
        source = _source(repo, watch, c['source_id'], now)
        quote = cal._text(c['quote'], 1000)
        if quote not in source['body'] or cal._at(source['available_at']) > now:
            raise ValueError('Exact available source quote required')
        verified.append({'source_id': source['source_id'], 'source_receipt_id': source['receipt_id'],
            'source_url': source['url'], 'quote': quote, 'published_at': source['published_at'],
            'captured_at': source['captured_at'], 'available_at': source['available_at']})
        if source['source_id'] == date_source_id and date_text in quote:
            date_source, date_quote = source, quote
    if not date_source or not isinstance(date_text, str) or not date_text:
        raise ValueError('The literal date must appear in the cited date source')
    if basis == 'EXPLICIT_FULL_DATE':
        if (date_text, day) not in date_mentions(date_quote):
            raise ValueError('An exact full source date is required')
    elif basis == 'PUBLICATION_DAY_TODAY':
        if (origin not in {'ASSISTANT_REVIEWED_SOURCE_DATE', 'LOCAL_OPERATOR_SOURCE_DATE_REVIEW'} or date_text.lower() != 'today'
                or not date_source['published_at']
                or cal._at(date_source['published_at']).astimezone(zone).date() != day):
            raise ValueError('Today requires a dated publication and explicit reviewed local timezone')
    else:
        raise ValueError('Unknown date basis')
    explanation = cal._text(explanation, 1500)
    identity = [watch_id, event_date, timezone_name, verified, date_source_id, date_text, basis, origin, explanation]
    return radar.save(repo, 'watch-timing', identity, {'watch_id': watch_id, 'parent_watch_id': watch.get('parent_watch_id'),
        'event_date': day.isoformat(), 'timezone': timezone_name,
        'timezone_basis': 'CONSERVATIVE_UNKNOWN_EVENT_TIMEZONE' if timezone_name == UNKNOWN_ZONE else 'REVIEWED_DATE_TIMEZONE',
        'expires_at': date_end(day, timezone_name).isoformat(), 'time_precision': 'DATE_ONLY_EVENT_TIME_UNKNOWN',
        'date_source_id': date_source_id, 'date_text': date_text, 'date_basis': basis,
        'citations': verified, 'explanation': explanation, 'origin': origin,
        'state': 'SOURCE_DATE_CANDIDATE_NOT_OCCURRENCE', 'automatic_occurrence_verdict': False}, now)


def expiry_policy(repo, watch_id, now):
    policies = [p for p in radar.rows(repo, 'watch-expiry-policy', now) if p['watch_id'] == watch_id]
    return max(policies, key=lambda p: (p['received_at'], p['record_id']), default=None)


@cal._write
def ensure_expiry_policy(repo, watch, now):
    """Record an actual rollout-time extension for a still-relevant legacy date."""
    now = cal._at(now)
    if repo.paper_record(watch['record_id']) != watch or cal._at(watch['received_at']) > now:
        raise ValueError('Saved watch already available required')
    if not watch.get('event_date'):
        return None
    corrected = date_end(watch['event_date'])
    if corrected <= cal._at(watch['expires_at']) or corrected <= now:
        return None
    identity = [VERSION, watch['record_id'], watch['expires_at'], corrected.isoformat()]
    rid = 'radar-watch-expiry-policy-' + cal._hash(identity)
    prior = repo.paper_record(rid)
    if prior:
        return prior if cal._at(prior['received_at']) <= now else None
    return radar.save(repo, 'watch-expiry-policy', identity, {'watch_id': watch['record_id'],
        'original_expires_at': watch['expires_at'], 'expires_at': corrected.isoformat(),
        'state': 'DATE_ONLY_EXPIRY_EXTENSION_RECORDED_AT_ACTUAL_TIME'}, now)


def effective_timeline(watch, timing=None, policy=None):
    """Project only date links or expiry extensions already recorded as of now."""
    if timing:
        return {'event_date': timing['event_date'], 'timezone': timing['timezone'],
                'expires_at': timing['expires_at'], 'timing_id': timing['record_id']}
    if watch.get('event_date'):
        expiry = policy['expires_at'] if policy else watch['expires_at']
        zone = UNKNOWN_ZONE if cal._at(expiry) >= date_end(watch['event_date']) else None
        return {'event_date': watch['event_date'], 'timezone': zone,
                'expires_at': expiry, 'timing_id': None}
    return {'event_date': None, 'timezone': None, 'expires_at': watch['expires_at'], 'timing_id': None}


def unresolved_conflicts(rows, watch_id, timing):
    return [c for c in rows if c['watch_id'] == watch_id
            and (not timing or cal._at(c['received_at']) > cal._at(timing['received_at']))]


def retain_through_conflicts(timeline, conflicts):
    """Keep a watch visible through the latest disputed date without selecting it."""
    dates = [date.fromisoformat(day) for conflict in conflicts for day in conflict['candidate_dates']]
    if not dates:
        return timeline
    deadline = max([cal._at(timeline['expires_at'])] + [date_end(day) for day in dates])
    return {**timeline, 'expires_at': deadline.isoformat(),
            'conflict_retention': 'THROUGH_LATEST_CANDIDATE_DATE_NOT_DATE_SELECTION'}


@cal._write
def split_watch(repo, watch_id, now):
    """Create distinct children from exact source fragments without moving clocks."""
    now = cal._at(now)
    parent = _watch(repo, watch_id, now)
    if parent.get('parent_watch_id'):
        return []
    parts = components_for(parent)
    if len(parts) < 2:
        return []
    source = _original_source(repo, parent)
    if not source or parent['quote'] not in source['body']:
        raise ValueError('Immutable original source packet required')
    scope = max(radar.rows(repo, 'scope', now), key=lambda x: x['received_at'], default={})
    members = scope.get('members', {})
    expiry = min(cal._at(parent['causal_cutoff']) + timedelta(hours=48), radar.news_expiry(source))
    children = []
    for part in parts:
        if any(fragment not in parent['quote'] for fragment in part['fragments']):
            raise ValueError('Every component fragment must occur in the original source')
        keys = radar.issuer_links(' '.join(part['fragments']), members)[:5]
        sectors = sorted({members[k]['sector'] for k in keys}) if keys else parent.get('topic_sectors', [])
        payload = {k: v for k, v in parent.items() if k not in {'record_id', 'schema', 'received_at'}}
        payload.update(parent_watch_id=parent['record_id'], component_fragments=part['fragments'],
            component_label=part['label'], component_origin='HOST_LITERAL_TEXT_SPLIT_NEEDS_REVIEW',
            kind='CONDITIONAL_WATCH', event_date=None, date_state='UNSCHEDULED_CONDITIONAL',
            time_precision='48_HOUR_WATCH_WINDOW_NOT_EVENT_DATE', expires_at=expiry.isoformat(),
            frozen_at=now.isoformat(), instrument_ids=keys, sectors=sectors,
            reason='Source mentions: ' + part['label'],
            failure_condition='Review this individual event and its date; expiry is not an occurrence verdict')
        child = radar.save(repo, 'watch', [VERSION, parent['record_id'], part['fragments']], payload, now)
        children.append(child)
        dates = date_mentions(part['dated_fragment'] or '')
        if len(dates) == 1 and date_end(dates[0][1]) > now:
            record_timing(repo, child['record_id'], dates[0][1].isoformat(), UNKNOWN_ZONE,
                [{'source_id': parent['source_id'], 'quote': part['dated_fragment']}],
                parent['source_id'], dates[0][0], 'The source fragment names this event and date; their association needs review.',
                now, origin='HOST_LITERAL_DATE_CANDIDATE')
    return children


def _words(text):
    text = _EVENT_RE.sub(' ', text)
    return [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9'-]*", text)
            if w.lower() not in _STOP]


def matches_component(watch, text):
    """Require both an event word and this component's identifying terms."""
    fragments = watch.get('component_fragments') or [watch.get('reason', '').removeprefix('Source mentions: ')]
    if not fragments or not _EVENT_RE.search(text):
        return False
    event_words = [m.group(0).lower() for f in fragments for m in _EVENT_RE.finditer(f)]
    if not event_words:
        return False
    def event_pattern(word):
        if word.startswith(('vot', 'election', 'midterm')):
            return r'(?:vot(?:e|es|ed|ing)|elections?|midterms?)'
        if 'rate ' in word:
            return r'(?:interest[-\s]*)?rate\s+(?:calls?|decisions?)'
        base = word[:-1] if word.endswith('s') else word
        return re.escape(base) + r's?'
    if not any(re.search(r'\b' + event_pattern(word) + r'\b', text, re.I) for word in event_words):
        return False
    identifiers = _words(' '.join(fragments))
    if not identifiers:
        return False
    def pattern(word):
        if word in {'israel', 'israeli'}:
            return r'israel(?:i)?'
        if word == 'us':
            return r'(?:us|u\.s\.|united\s+states)'
        if word == 'fed':
            return r'(?:fed|federal\s+reserve)'
        return re.escape(word)
    return all(re.search(r'(?<!\w)' + pattern(w) + r'(?!\w)', text, re.I) for w in identifiers)


def source_date_candidate(watch, text):
    """Find one future explicit date in the same event-specific sentence."""
    candidates = []
    for sentence in re.split(r'[\n;!?]+|(?<!\bU)(?<!\bS)\.\s+', text):
        sentence = sentence.strip()
        if not sentence or len(sentence) > 1000 or not matches_component(watch, sentence):
            continue
        # Adjacent event nouns can describe one event (for example, an
        # earnings release). Separated event nouns may name different events,
        # so do not attach their shared sentence date without review.
        terms = list(_EVENT_RE.finditer(sentence))
        if not terms or any(not re.fullmatch(r'\s*', sentence[a.end():b.start()])
                            for a, b in zip(terms, terms[1:])):
            continue
        dates = date_mentions(sentence)
        if len(dates) != 1:
            continue
        literal, day = dates[0]
        before = sentence[:sentence.index(literal)]
        if not re.search(r'\b(?:on|for|scheduled(?:\s+for)?|due(?:\s+on)?|set(?:\s+for)?|'
                         r'takes?\s+place(?:\s+on)?|follows?(?:\s+on)?)\s*$', before, re.I):
            continue
        candidates.append((sentence, literal, day))
    unique = {(literal, day) for _, literal, day in candidates}
    return candidates[0] if len(unique) == 1 else None
