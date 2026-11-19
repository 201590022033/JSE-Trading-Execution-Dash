"""Compare retained daily volume observations without changing Zebra selection."""
from collections import Counter, defaultdict, deque
from statistics import mean, median

from .zebra_screen_data import _time, _value
from .session_freshness import next_session


def reconcile_volume(rows, *, as_of=None):
    def visible(item):
        try:
            return as_of is None or _time(item.get('acquired_at')) <= as_of
        except (TypeError, ValueError):
            return False

    selected_sources = Counter()
    pairs = defaultdict(list)
    provider_windows = {}
    zebra_window = deque(maxlen=20)
    comparisons = defaultdict(Counter)
    sample = None
    previous = None
    for row in sorted(rows, key=lambda item: item['session']):
        day = row['session']
        if previous is not None and next_session(previous) != day:
            provider_windows.clear()
            zebra_window.clear()
        previous = day
        chosen = (row.get('fields') or {}).get('volume') or {}
        selected = _value(chosen.get('value'), 'volume')
        source = chosen.get('source')
        if selected is None or not source or not visible(chosen):
            provider_windows.clear()
            zebra_window.clear()
            continue
        selected_sources[source] += 1
        others = {}
        alternatives = []
        for candidate in chosen.get('alternatives') or []:
            provider = candidate.get('source')
            value = _value(candidate.get('value'), 'volume')
            if provider and provider != source and value is not None and visible(candidate):
                others[provider] = value
                alternatives.append(candidate)
                pairs[(source, provider)].append((selected, value))
        observations = {**others, source: selected}
        prior = (median(zebra_window) or mean(zebra_window)) if len(zebra_window) == 20 else None
        for provider, value in observations.items():
            history = provider_windows.setdefault(provider, deque(maxlen=20))
            provider_prior = (median(history) or mean(history)) if len(history) == 20 else None
            if prior is not None and provider_prior is not None:
                comparisons[provider]['sessions'] += 1
                comparisons[provider]['rule_flips'] += (selected > prior) != (value > provider_prior)
            history.append(value)
        provider_windows = {provider: history for provider, history in provider_windows.items()
                            if provider in observations}
        zebra_window.append(selected)
        if others and any(value != selected for value in others.values()):
            keys = ('source', 'value', 'acquired_at', 'source_sha256', 'field_source_sha256')
            sample = {'session': day, 'selection_state': chosen.get('state'),
                      'observations': [{key: item.get(key) for key in keys}
                                       for item in (chosen, *alternatives)]}
    pair_results = []
    for (selected_source, other_source), values in sorted(pairs.items()):
        relative = [(selected / other - 1) * 100 for selected, other in values if other > 0]
        pair_results.append({'selected_source': selected_source, 'other_source': other_source,
                             'matched_sessions': len(values), 'equal': sum(a == b for a, b in values),
                             'selected_higher': sum(a > b for a, b in values),
                             'median_difference_pct': round(median(relative), 3) if relative else None})
    return {'selected_sources': dict(selected_sources), 'pairs': pair_results,
            'volume_rule_sensitivity': dict(comparisons), 'latest_disagreement': sample,
            'volume_rule': 'CURRENT_VOLUME_ABOVE_PRIOR_20_MEDIAN',
            'scope': 'RETAINED_PROVIDER_VALUES_AND_CLOCKS',
            'provider_volume_definition': 'UNVERIFIED'}
