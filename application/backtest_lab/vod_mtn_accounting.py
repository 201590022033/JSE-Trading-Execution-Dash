"""Independent cash ledgers over verified prospective W06 receipts."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256

from application.backtest_lab.forward_monitor import _visible_rows
from application.backtest_lab.observed_history import ObservedHistory
from domain.backtest.component_engine import Costs, Signal, replay
from domain.backtest.data import Bar, Session


def account(plan, instrument, records):
    sizing = plan['sizing']
    costs = Costs(**plan['costs'])
    segments = []
    current = []
    unavailable = 0
    for day in plan['sessions']:
        record = records.get(day)
        row = None
        if record:
            receipt, packet = record
            visible = _visible_rows(packet['share'], receipt['cutoff'])
            if visible and visible[-1]['timestamp'] == day:
                row = visible[-1]
        keys = ('open','high','low','close','volume')
        if row and all(k in row for k in keys):
            current.append((receipt,row))
        else:
            unavailable += record is not None
            if current:
                segments.append(current)
                current = []
    if current:
        segments.append(current)
    results = []
    for segment in segments:
        sessions, bars = [], []
        for receipt, row in segment:
            day = datetime.fromisoformat(receipt['session']).replace(tzinfo=timezone.utc)
            sessions.append(Session(receipt['session'],day+timedelta(hours=7),day+timedelta(hours=15)))
            bars.append(Bar(receipt['session'],datetime.fromisoformat(receipt['observed_at']),
                            *(Decimal(str(row[key])) for key in keys)))
        last = segment[-1][0]['observed_at']
        source = sha256(''.join(receipt['input_sha256'] for receipt,_ in segment).encode()).hexdigest()
        manifest = ObservedHistory(instrument,'ZEBRA_FORWARD_RECEIPTS',source,last,tuple(sessions),tuple(bars),
                                   availability_basis='ACTUAL_CAPTURE_CLOCK',calendar_basis='FROZEN_JSE_SESSIONS')
        arms = {}
        for arm, identity in plan['arms'].items():
            strategy, version = identity.split('@')
            signals = []
            for receipt,_ in segment:
                decision = receipt['arms'][arm]
                stop = decision.get('stop' if arm=='A' else 'stop_reference')
                expected = 'SIGNAL' if arm=='A' else 'TRIGGERED'
                if decision['state']==expected and stop is not None:
                    signals.append(Signal(receipt['session'],instrument,receipt['session'],
                        datetime.fromisoformat(receipt['observed_at']),Decimal(str(stop)),
                        Decimal(sizing['max_notional']),Decimal(sizing['risk_budget']),
                        horizon=sizing['horizon'],target_r=Decimal(sizing['target_r']),
                        strategy_profile_id=strategy,strategy_profile_version=version))
            output = replay((manifest,),signals,as_of=datetime.fromisoformat(last),
                            initial_cash=Decimal(sizing['initial_cash']),costs=costs)
            arms[arm] = dict(signals=len(signals), closed=len(output['trades']),
                             net_closed_zar=str(sum((Decimal(t['net_pnl']) for t in output['trades']), Decimal(0))),
                             open_positions=len(output['open_positions']), pending_orders=len(output['pending_orders']),
                             engine_config_hash=output['config_hash'])
        results.append(dict(first=sessions[0].key,last=sessions[-1].key,arms=arms))
    return dict(state='OBSERVED_ONLY' if results else 'AWAITING_INPUTS',
                unavailable_price_receipts=unavailable,segments=results)
