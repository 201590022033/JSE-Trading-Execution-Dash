"""Explicit inactive frozen Swing adapter. No accounts, fills or activation."""
from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from jse_intelligence_core.json_boundary import canonical, digest, exact, parse_json
from domain.policy.swing_shadow import build_policy, rules, VERSION, PROFILE, FEATURE_PROFILE
from jse_intelligence_core import SectorScope, StrategyMapping, StrategyRelease
from jse_intelligence_core.contracts import _instant, _day

API = 'inactive-swing-evaluator/1'
FEATURES = 'frozen-swing-policy-input/1'
FEATURE_FIELDS = ('version', 'strategy_profile_id', 'strategy_profile_version', 'state', 'evaluated_at',
                  'session', 'available_at', 'last_close', 'source_symbol', 'values', 'missing', 'conditions')
VALUES = ('atr14_wilder', 'prior_low10')
CONDITIONS = ('ema_uptrend', 'rsi_50_70', 'volume_above_prior20', 'outperforming_benchmark20',
              'breakout20', 'ema20_reclaim', 'core_setup')


class StrategyError(ValueError):
    pass


def need(value, code):
    if not value:
        raise StrategyError(code)


def instant(value):
    return datetime.fromisoformat(_instant(value).replace('Z', '+00:00'))


def bounded(value):
    # Same finite/size/depth limits as the established X2 JSON protocol.
    return parse_json(value if type(value) is bytes else canonical(value).encode())


def component_parameters():
    r = rules()
    return {
        'entry': {k: r[k] for k in ('entry', 'entry_expiry_calendar_days', 'setup')},
        'exit': {k: r[k] for k in ('exit', 'target_r_multiple', 'same_bar', 'gap_stop', 'gap_target', 'entry_bar', 'holding')},
        'stop': {k: r[k] for k in ('stop', 'trailing')},
        'timeline': dict(frequency='1d', entry=r['entry'], holding=r['holding'], clock='COMPLETED_FEATURE_AVAILABILITY'),
        'volume': dict(role='SETUP_GATE', minimum_exclusive=1),
        'risk': dict(role='EXECUTION_OWNED_RISK_REVIEW', sizing='NONE', order_authority=False),
    }


def policy_intent(features, decision_at, horizon):
    """Call the installed versioned policy; do not reimplement setup/stop math."""
    exact(features, FEATURE_FIELDS)
    need(features['version'] == 'swing-ohlcv-wilder-v1'
         and (features['strategy_profile_id'], features['strategy_profile_version']) ==
         (FEATURE_PROFILE.strategy_profile_id, FEATURE_PROFILE.strategy_profile_version), 'UNSUPPORTED_FEATURES')
    need(type(features['source_symbol']) is str and bool(features['source_symbol']), 'INVALID_FEATURES')
    _day(features['session'])
    need(instant(features['available_at']) <= instant(features['evaluated_at']) <= instant(decision_at), 'FUTURE_FEATURES')
    need(features['session'] <= instant(features['available_at']).date().isoformat(), 'FUTURE_SESSION')
    need(features['state'] in ('AVAILABLE', 'PARTIAL', 'UNAVAILABLE'), 'INVALID_FEATURES')
    need(type(features['missing']) is list and len(features['missing']) <= 32 and
         all(type(x) is str and 0 < len(x) <= 100 for x in features['missing']), 'INVALID_FEATURES')
    exact(features['values'], VALUES)
    exact(features['conditions'], CONDITIONS)
    for value in (features['last_close'], *features['values'].values()):
        need(value is None or (type(value) in (int, float) and 0 < value <= 1e9 and math.isfinite(value)), 'INVALID_FEATURES')
    need(all(v is None or type(v) is bool for v in features['conditions'].values()), 'INVALID_FEATURES')
    if features['state'] == 'AVAILABLE' and not features['missing']:
        need(all(v is not None for v in (features['last_close'], *features['values'].values(), *features['conditions'].values())), 'INVALID_FEATURES')
    # Decimal setup thresholds and feature calculation remain upstream, supplied
    # by the trusted consumer feature producer, never asserted by the release.
    policy = build_policy(features, decision_at=_instant(decision_at))
    intent = None
    if policy['state'] == 'SHADOW_READY':
        intent = dict(direction='LONG', signal_session=policy['signal_session'], signal_close=policy['signal_close'],
                      entry=policy['rules']['entry'], stop_price=policy['stop_price'],
                      target_r_multiple=policy['rules']['target_r_multiple'], horizon_sessions=int(horizon[-1]),
                      expires_at=(instant(decision_at)+timedelta(days=7)).isoformat().replace('+00:00', 'Z'),
                      requires_risk_review=True)
    return dict(state='INTENT' if intent else 'NO_SETUP' if policy['state'] == 'NO_SETUP' else 'UNAVAILABLE',
                reason_code=policy['reasons'][0], policy=policy, intent=intent,
                execution_enabled=False, live_execution=False, order_intent=None)


@dataclass(frozen=True, slots=True)
class InactiveStrategy:
    package_json: str
    package_id: str
    manifest_id: str
    test_only: bool
    state: str = 'INACTIVE'


class StrategyEvaluator:
    def __init__(self, *, scope, mappings, source_ids, test_only=False, allow_test_releases=False):
        # These are explicit consumer configuration, never taken from a package.
        self.scope = SectorScope.from_dict(scope)
        need(type(mappings) is list and 1 <= len(mappings) <= 32, 'INVALID_MAPPINGS')
        self.mappings = tuple(StrategyMapping.from_dict(m) for m in mappings)
        need(len({m.research_instrument_id for m in self.mappings}) == len(self.mappings)
             and len({m.execution_instrument_id for m in self.mappings}) == len(self.mappings)
             and len({m.source_symbol for m in self.mappings}) == len(self.mappings), 'INVALID_MAPPINGS')
        need(all(m.mapping_state == 'reviewed_exact' and m.product_type == 'cash_share'
                 and self.scope.permits(m.research_instrument_id, m.product_type) for m in self.mappings), 'UNSUPPORTED_PRODUCT_OR_MAPPING')
        need(type(source_ids) is list and 1 <= len(source_ids) <= 32 and
             all(type(s) is str and s for s in source_ids) and len(set(source_ids)) == len(source_ids), 'INVALID_SOURCES')
        need(type(allow_test_releases) is bool and type(test_only) is bool, 'INVALID_TEST_POLICY')
        self.sources = tuple(source_ids)
        self.allow_test = allow_test_releases
        self.test_only = test_only

    @staticmethod
    def capabilities():
        return dict(evaluator_version=API, feature_schema_version=FEATURES, strategy_id=PROFILE.strategy_profile_id,
                    strategy_version=PROFILE.strategy_profile_version, data_frequency='1d',
                    products=['cash_share'], horizons=['sessions_3', 'sessions_4', 'sessions_5'],
                    component_parameters=component_parameters(), activation=False, account_sizing=False)

    def prepare(self, package):
        package = bounded(package)
        exact(package, ('schema_version', 'manifest', 'expected_manifest_id', 'artifacts'))
        need(package['schema_version'] == 'inactive-strategy-package/1', 'UNSUPPORTED_PACKAGE')
        manifest = StrategyRelease.from_dict(package['manifest'], expected_id=package['expected_manifest_id'])
        need(not (manifest.test_only or self.test_only) or self.allow_test, 'TEST_RELEASE_DISABLED')
        need((manifest.strategy_id, manifest.strategy_version) ==
             (PROFILE.strategy_profile_id, PROFILE.strategy_profile_version), 'UNSUPPORTED_STRATEGY')
        need(manifest.evaluator_version == API and manifest.feature_schema_version == FEATURES, 'UNSUPPORTED_CAPABILITY')
        need(manifest.data_frequency == '1d' and manifest.horizon in ('sessions_3', 'sessions_4', 'sessions_5')
             and manifest.missing_data_policy == 'BLOCK_NEW_INTENT', 'UNSUPPORTED_TIMELINE')
        need(manifest.scope == self.scope, 'UNSUPPORTED_SCOPE')
        need(all(m in self.mappings and m.mapping_state == 'reviewed_exact' and m.product_type == 'cash_share'
                 for m in manifest.mappings), 'UNSUPPORTED_PRODUCT_OR_MAPPING')
        refs = (manifest.code_reference, manifest.configuration_reference, manifest.outcome_reference,
                manifest.parity_reference, *manifest.evidence_references, *(c.parameters for c in manifest.components),
                manifest.scope.universe, manifest.scope.exposures, *manifest.scope.context_references)
        by_ref = {}
        for ref in refs:
            need(ref.reference_id not in by_ref or by_ref[ref.reference_id] == ref.content_hash, 'REFERENCE_CONFLICT')
            by_ref[ref.reference_id] = ref.content_hash
        need(type(package['artifacts']) is list and len(package['artifacts']) == len(by_ref) <= 64, 'INCOMPLETE_PACKAGE')
        data = {}
        for artifact in package['artifacts']:
            exact(artifact, ('reference_id', 'raw_json'))
            rid, raw = artifact['reference_id'], artifact['raw_json']
            need(type(rid) is str and rid in by_ref and rid not in data and type(raw) is str, 'INVALID_ARTIFACT')
            need(digest(raw.encode()) == by_ref[rid], 'ARTIFACT_INTEGRITY')
            wrapper = parse_json(raw.encode())
            exact(wrapper, ('schema_version', 'data'))
            need(wrapper['schema_version'] == 'strategy-inert-data/1', 'UNSUPPORTED_ARTIFACT')
            data[rid] = wrapper['data']
        for c in manifest.components:
            need(c.component_id == 'swing-'+c.role and c.component_version == VERSION, 'UNSUPPORTED_COMPONENT')
            need(canonical(data[c.parameters.reference_id]) == canonical(component_parameters()[c.role]), 'UNSUPPORTED_PARAMETERS')
        need(canonical(data[manifest.code_reference.reference_id]) == canonical(dict(policy_version=VERSION, rules=rules())), 'UNSUPPORTED_CODE')
        need(data[manifest.configuration_reference.reference_id] == dict(horizon=manifest.horizon, currency='ZAR', mode='INACTIVE'), 'UNSUPPORTED_CONFIGURATION')
        # Evidence/outcome bytes are retained and bound, not a performance signoff.
        parity = data[manifest.parity_reference.reference_id]
        exact(parity, ('schema_version', 'cases'))
        need(parity['schema_version'] == 'strategy-parity/1' and type(parity['cases']) is list
             and 3 <= len(parity['cases']) <= 32, 'INVALID_PARITY')
        ids = set()
        for case in parity['cases']:
            exact(case, ('case_id', 'features', 'decision_at', 'expected'))
            need(type(case['case_id']) is str and case['case_id'] not in ids, 'INVALID_PARITY')
            ids.add(case['case_id'])
            need(case['features']['source_symbol'] in {m.source_symbol for m in manifest.mappings}, 'SOURCE_MAPPING_MISMATCH')
            need(canonical(policy_intent(case['features'], case['decision_at'], manifest.horizon)) == canonical(case['expected']), 'PARITY_MISMATCH')
        need({'setup', 'no_setup', 'missing'} <= ids, 'INVALID_PARITY')
        raw = canonical(package)
        return InactiveStrategy(raw, digest(raw.encode()), manifest.canonical_id, manifest.test_only or self.test_only)

    def evaluate(self, candidate, snapshot, admission, *, as_of):
        need(type(candidate) is InactiveStrategy and candidate.state == 'INACTIVE', 'INACTIVE_CANDIDATE_REQUIRED')
        verified = self.prepare(candidate.package_json.encode())
        need(verified == candidate, 'CANDIDATE_INTEGRITY')
        manifest = StrategyRelease.from_dict(parse_json(candidate.package_json.encode())['manifest'])
        snapshot, admission = bounded(snapshot), bounded(admission)
        exact(snapshot, ('schema_version', 'scope_id', 'mapping', 'horizon', 'features', 'dependencies'))
        need(snapshot['schema_version'] == 'strategy-current/1', 'UNSUPPORTED_SNAPSHOT')
        mapping = StrategyMapping.from_dict(snapshot['mapping'])
        need(snapshot['scope_id'] == manifest.scope.scope_id and mapping in manifest.mappings, 'OUT_OF_SCOPE')
        need(snapshot['horizon'] == manifest.horizon, 'UNSUPPORTED_HORIZON')
        now = instant(as_of)
        need(instant(manifest.created_at) <= now and all(datetime.fromisoformat(r.as_of).date() <= now.date()
             for r in (manifest.scope.universe, manifest.scope.exposures)), 'FUTURE_RELEASE_OR_SCOPE')
        result = dict(schema_version='inactive-strategy-evaluation/1', manifest_id=manifest.canonical_id,
                      package_id=candidate.package_id, strategy_id=manifest.strategy_id, strategy_version=manifest.strategy_version,
                      component_references=[c.to_dict() for c in manifest.components], mapping=mapping.to_dict(),
                      horizon=manifest.horizon, as_of=_instant(as_of), snapshot_id=digest(canonical(snapshot).encode()),
                      admission_id=digest(canonical(admission).encode()), input_available_at=None,
                      test_only=candidate.test_only, candidate_state='INACTIVE', state='UNAVAILABLE',
                      reason_code=None, intent=None, policy=None, execution_enabled=False, live_execution=False, order_intent=None)
        try:
            need(snapshot['features']['source_symbol'] == mapping.source_symbol, 'SOURCE_MAPPING_MISMATCH')
            exact(admission, ('enabled', 'admissible', 'observed_at', 'mapping', 'scope_id'))
            need(admission['enabled'] is True and admission['admissible'] is True
                 and admission['mapping'] == mapping.to_dict() and admission['scope_id'] == manifest.scope.scope_id, 'NOT_ADMITTED')
            need(0 <= (now-instant(admission['observed_at'])).total_seconds() <= 60, 'STALE_ADMISSION')
            deps = snapshot['dependencies']
            need(type(deps) is list and len(deps) == 2, 'DEPENDENCIES_REQUIRED')
            roles = set()
            for dep in deps:
                exact(dep, ('role', 'source_id', 'content_hash', 'available_at', 'acquired_at', 'received_at'))
                need(dep['role'] in ('instrument', 'benchmark') and dep['role'] not in roles, 'DEPENDENCIES_REQUIRED')
                roles.add(dep['role'])
                from jse_intelligence_core import ArtifactReference
                ArtifactReference(reference_id=dep['source_id'], content_hash=dep['content_hash'])
                need(dep['source_id'] in self.sources, 'UNSUPPORTED_SOURCE')
                available, acquired, received = (instant(dep[k]) for k in ('available_at', 'acquired_at', 'received_at'))
                need(available <= acquired <= received <= now and 0 <= (now-available).total_seconds() <= 4*86400, 'STALE_OR_FUTURE_DEPENDENCY')
                need(received <= instant(snapshot['features']['evaluated_at'])
                     and available <= instant(snapshot['features']['available_at']), 'DEPENDENCY_AFTER_FEATURE')
            need(0 <= (now-instant(snapshot['features']['available_at'])).total_seconds() <= 4*86400, 'STALE_OR_FUTURE_FEATURES')
            result['input_available_at'] = max(instant(snapshot['features']['available_at']),
                *(instant(d['received_at']) for d in deps)).isoformat().replace('+00:00', 'Z')
            result.update(policy_intent(snapshot['features'], _instant(as_of), manifest.horizon))
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            result.update(state='UNAVAILABLE', reason_code=str(exc), intent=None, policy=None)
        return result
