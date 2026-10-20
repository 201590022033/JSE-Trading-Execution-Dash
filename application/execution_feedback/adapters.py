"""Explicit source-record projections, never collection or order submission."""
from dataclasses import asdict
from decimal import Decimal

from jse_intelligence_core import ArtifactReference, ExecutionFeedback, PublicationClock, StrategyRelease
from jse_intelligence_core.contracts import _instant
from jse_intelligence_core.feedback import identifier
from jse_intelligence_core.json_boundary import canonical, digest, parse_json
from .journal import need


def inactive_decision_feedback(candidate, evaluation, *, event_id, producer_id, producer_sequence,
                               decision_id, observed_at, recorded_at):
    """Project a supplied X4 result. No active strategy or account is implied."""
    from application.strategy_releases import InactiveStrategy
    need(type(candidate) is InactiveStrategy and candidate.state == 'INACTIVE', 'INACTIVE_CANDIDATE_REQUIRED')
    package = parse_json(candidate.package_json.encode())
    manifest = StrategyRelease.from_dict(package['manifest'], expected_id=candidate.manifest_id)
    need(evaluation['mapping'] in [m.to_dict() for m in manifest.mappings]
         and evaluation['horizon'] == manifest.horizon, 'DECISION_SCOPE_MISMATCH')
    need(digest(canonical(package).encode()) == candidate.package_id
         and evaluation['manifest_id'] == candidate.manifest_id and evaluation['package_id'] == candidate.package_id,
         'DECISION_RELEASE_MISMATCH')
    need(evaluation['candidate_state'] == 'INACTIVE' and evaluation['execution_enabled'] is False
         and evaluation['live_execution'] is False and evaluation['order_intent'] is None
         and evaluation['state'] in ('INTENT','NO_SETUP','UNAVAILABLE'), 'INACTIVE_DECISION_REQUIRED')
    reason = evaluation['reason_code']
    try:
        identifier(reason)
    except ValueError:
        reason = 'EVALUATOR_UNAVAILABLE'
    return ExecutionFeedback.from_dict(dict(schema_version='execution-feedback/1', event_id=event_id,
        producer_id=producer_id, producer_sequence=producer_sequence, release_id=manifest.canonical_id,
        package_id=candidate.package_id, mapping=evaluation['mapping'], horizon=evaluation['horizon'],
        decision_id=decision_id, kind='DECISION', provenance='PAPER_SIMULATED',
        occurrence=dict(value=evaluation['as_of'],precision='exact',timezone_state='offset_known',basis='source_asserted'),
        clock_source='consumer:inactive-strategy-evaluation', observed_at=observed_at, recorded_at=recorded_at,
        source_reference=dict(reference_id='consumer:evaluation',content_hash=digest(canonical(evaluation).encode())),
        parent=None, correction_of=None, data_json=canonical(dict(status=evaluation['state'],reason_code=reason,
            snapshot_id=evaluation['snapshot_id'],admission_id=evaluation['admission_id'])),
        test_only=candidate.test_only or evaluation['test_only']))


def paper_fill_feedback(fill, order_event, manifest, *, fill_event_id, cost_event_id,
                        first_sequence, observed_at, recorded_at, currency):
    """Project a supplied PaperFill as simulated fill/cost, never broker-confirmed."""
    from domain.broker.paper import PaperFill
    need(type(fill) is PaperFill and type(order_event) is ExecutionFeedback and order_event.kind == 'ORDER'
         and order_event.provenance == 'PAPER_SIMULATED', 'PAPER_FILL_SOURCE_REQUIRED')
    manifest = StrategyRelease.from_dict(manifest, expected_id=order_event.release_id)
    need((fill.strategy_profile_id,fill.strategy_profile_version) == (manifest.strategy_id,manifest.strategy_version)
         and fill.instrument_id == order_event.mapping.execution_instrument_id
         and fill.order_id == order_event.data['order_id'], 'PAPER_FILL_LINEAGE_MISMATCH')
    need(fill.direction in ('LONG','SHORT'), 'UNSUPPORTED_PAPER_SIDE')
    source = asdict(fill)
    source['filled_at'] = _instant(fill.filled_at.isoformat())
    source['currency_context'] = currency
    reference = ArtifactReference(reference_id=fill.fill_id,content_hash=digest(canonical(source).encode()))
    occurrence = PublicationClock(value=source['filled_at'],precision='exact',timezone_state='offset_known',basis='source_asserted')
    def number(value):
        # Preserve supplied decimal representation. Excess precision rejects in
        # the contract rather than silently rounding a financial observation.
        return format(Decimal(str(value)), 'f')
    common = dict(producer_id=order_event.producer_id,release_id=order_event.release_id,
        package_id=order_event.package_id,mapping=order_event.mapping,horizon=order_event.horizon,
        decision_id=order_event.decision_id,provenance='PAPER_SIMULATED',occurrence=occurrence,
        clock_source='paper:supplied-fill',observed_at=observed_at,recorded_at=recorded_at,
        source_reference=reference,correction_of=None,test_only=order_event.test_only or manifest.test_only)
    observed_fill = ExecutionFeedback(event_id=fill_event_id,producer_sequence=first_sequence,kind='FILL',
        parent=ArtifactReference(reference_id=order_event.event_id,content_hash=order_event.canonical_id),
        data_json=canonical(dict(fill_id=fill.fill_id,order_id=fill.order_id,side='BUY' if fill.direction == 'LONG' else 'SELL',
            quantity=number(fill.quantity),price=number(fill.fill_price),currency=currency)),**common)
    cost = ExecutionFeedback(event_id=cost_event_id,producer_sequence=first_sequence+1,kind='COST',
        parent=ArtifactReference(reference_id=observed_fill.event_id,content_hash=observed_fill.canonical_id),
        data_json=canonical(dict(cost_id=fill.fill_id+':cost',currency=currency,commission=number(fill.transaction_cost),
            slippage=number(fill.slippage),other=None,basis='HYPOTHETICAL')),**common)
    return observed_fill,cost
