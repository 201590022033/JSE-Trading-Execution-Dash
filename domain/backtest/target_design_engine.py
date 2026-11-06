"""Deterministic close-proxy daily cash replay, versioned away from Swing 1.2.0."""
from dataclasses import dataclass, asdict, replace
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP, localcontext
from domain.backtest.data import number as N
from domain.evaluation.experiment import configuration_hash, utc

VERSION = 'target-design-replay-v1'
ZERO = Decimal(0)


def money(x):
    return x.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Costs:
    fee_bps: Decimal = ZERO
    minimum_fee: Decimal = ZERO
    spread_bps: Decimal = ZERO
    slippage_bps: Decimal = ZERO
    basis: str = 'HYPOTHETICAL_NOT_BROKER_VERIFIED'

    def __post_init__(self):
        for name in ('fee_bps', 'minimum_fee', 'spread_bps', 'slippage_bps'):
            value = N(getattr(self, name))
            if value < 0: raise ValueError('nonnegative explicit costs required')
            object.__setattr__(self, name, value)
        if not self.basis: raise ValueError('cost provenance required')

    def fill(self, price, direction):
        return price * (1 + direction * (self.spread_bps/2+self.slippage_bps)/10000)

    def fee(self, notional, direction=1):
        return money(max(self.minimum_fee, abs(notional)*self.fee_bps/10000))

    def validate(self, manifests):
        """Generic hypothetical costs have no broker/product applicability claim."""


@dataclass(frozen=True)
class Signal:
    id: str
    instrument: str
    session: str
    decision_at: datetime
    stop: Decimal
    max_notional: Decimal
    risk_budget: Decimal
    horizon: int = 3
    target_r: Decimal | None = Decimal(2)
    trail: str = 'NONE'
    atr_period: int = 14
    trail_k: Decimal = Decimal('1.5')
    trail_activation_r: Decimal = Decimal(1)
    exit_mode: str = 'HORIZON_OR_TARGET'
    expiry_days: int = 7
    side: int = 1
    strategy_profile_id: str | None = None
    strategy_profile_version: str | None = None
    target_distance: Decimal | None = None
    target_policy: str = 'UNCHANGED'
    target_min_net_r: Decimal = Decimal(1)

    def __post_init__(self):
        object.__setattr__(self, 'decision_at', utc(self.decision_at, 'decision_at'))
        if bool(self.strategy_profile_id)!=bool(self.strategy_profile_version):
            raise ValueError('exact profile identity/version pair required')
        for name in ('stop', 'max_notional', 'risk_budget', 'trail_k', 'trail_activation_r'):
            value = N(getattr(self, name))
            if value <= 0: raise ValueError('positive geometry and budgets required')
            object.__setattr__(self, name, value)
        if self.target_r is not None:
            object.__setattr__(self, 'target_r', N(self.target_r))
            if self.target_r <= 0: raise ValueError('positive target required')
        if self.target_distance is not None:
            object.__setattr__(self, 'target_distance', N(self.target_distance))
            if self.target_distance <= 0: raise ValueError('positive projected distance required')
        object.__setattr__(self,'target_min_net_r',N(self.target_min_net_r))
        if self.target_policy not in ('UNCHANGED','FLOOR','REJECT') or self.target_min_net_r < 0:
            raise ValueError('supported research target policy and nonnegative minimum required')
        if not self.id or self.horizon not in (3,4,5) or self.side not in (1,-1):
            raise ValueError('identity, side and 3/4/5 horizon required')
        if self.exit_mode not in ('HORIZON_OR_TARGET','EMA21_CLOSE'):
            raise ValueError('unsupported component exit')
        if self.trail not in ('NONE','ATR','STRUCTURE') or self.atr_period < 1 or self.expiry_days < 1:
            raise ValueError('bounded explicit trail/expiry required')


@dataclass(frozen=True)
class Action:
    instrument: str
    session: str
    split: Decimal = Decimal(1)
    dividend: Decimal = ZERO

    def __post_init__(self):
        object.__setattr__(self, 'split', N(self.split))
        object.__setattr__(self, 'dividend', N(self.dividend))
        if self.split <= 0 or self.dividend < 0: raise ValueError('invalid action')


def atr(bars, period):
    if len(bars) <= period: return None
    ranges = [max(N(b.high)-N(b.low), abs(N(b.high)-N(a.close)), abs(N(b.low)-N(a.close)))
              for a,b in zip(bars,bars[1:])]
    value = sum(ranges[:period])/period
    for r in ranges[period:]: value = ((period-1)*value+r)/period
    return value


def ema_close(history, period):
    value=N(history[0].close); alpha=Decimal(2)/Decimal(period+1)
    for bar in history[1:]: value=alpha*N(bar.close)+(1-alpha)*value
    return value


class CashEquity:
    """Full-fill toy/research liquidity envelope, cash LONG only, integer shares."""
    version = 'cash-equity-v1'
    multiplier = Decimal(1)
    lot = Decimal(1)
    margin_fraction = Decimal(1)
    allow_short = False
    activity_required = True

    def validate(self, manifest):
        if manifest.product != 'EQUITY': raise ValueError('cash equity identity required')

    def rate(self, session): return Decimal(1)
    def financing(self, position, session, previous): return ZERO
    def configuration(self):
        return dict(version=self.version, multiplier=str(self.multiplier), lot=str(self.lot), margin_fraction=str(self.margin_fraction))


def replay(manifests, signals, *, as_of, initial_cash, account_currency='ZAR',
           costs=Costs(), actions=(), adapters=None):
    with localcontext() as context:
        context.prec=28
        context.rounding=ROUND_HALF_UP
        return _replay(manifests,signals,as_of=as_of,initial_cash=initial_cash,
                       account_currency=account_currency,costs=costs,actions=actions,adapters=adapters)


def _replay(manifests, signals, *, as_of, initial_cash, account_currency,
            costs, actions, adapters):
    """Pure function; restart by replaying frozen inputs. All fills are hypothetical.

    Orders reserve max_notional at signal time; same-timestamp ID breaks ties.
    Entry uses first later completed close, refusing pre-close stop invalidation.
    Entry session does not count toward horizon. Carried exits precede new orders.
    Margin adapters settle P&L; cash adapters debit/credit notional. Open lots stay
    marked, never silently liquidated at end of data. Sale proceeds usable only
    once the completed bar is available. No partial-fill claims are supported.
    """
    now = utc(as_of, 'as_of'); initial = money(N(initial_cash))
    if initial <= 0: raise ValueError('positive initial cash required')
    manifests = tuple(manifests); signals = tuple(signals); actions = tuple(actions)
    costs.validate(manifests)
    by_id = {m.instrument:m for m in manifests}
    if len(by_id) != len(manifests) or len({s.id for s in signals}) != len(signals):
        raise ValueError('duplicate instrument or signal identity')
    adapters = adapters or {m.instrument:CashEquity() for m in manifests}
    rows = {}; schedule = {}; events = []; histories = {k:[] for k in by_id}
    for m in manifests:
        adapter = adapters[m.instrument]; adapter.validate(m)
        if m.currency != account_currency and type(adapter) is CashEquity:
            raise ValueError('explicit conversion adapter required')
        if hasattr(adapter,'account_currency') and adapter.account_currency!=account_currency:
            raise ValueError('adapter account currency mismatch')
        if not m.sessions: raise ValueError('calendar required')
        rows[m.instrument] = m.admit(m.sessions[0].key,m.sessions[-1].key,now,
                                    activity_required=adapter.activity_required)
        schedule[m.instrument] = {s.key:s for s in m.sessions}
        events.extend((b.available_at,1,m.instrument,b) for b in rows[m.instrument])
    for s in signals:
        if s.instrument not in by_id or s.session not in schedule[s.instrument]: raise ValueError('signal source missing')
        session = schedule[s.instrument][s.session]
        visible = [b for b in rows[s.instrument] if b.session == s.session]
        if s.decision_at < session.close_at or (visible and s.decision_at < visible[0].available_at):
            raise ValueError('signal precedes available source')
        if s.decision_at <= now:
            if not visible: raise ValueError('signal source not observable')
            events.append((s.decision_at,2,s.id,s))
    action_map = {}
    for a in actions:
        if a.instrument not in by_id or a.session not in schedule[a.instrument] or by_id[a.instrument].action_basis != 'EXPLICIT':
            raise ValueError('actions require explicit manifest treatment')
        key=(a.instrument,a.session)
        if key in action_map: raise ValueError('duplicate corporate action')
        action_map[key]=a
    cash=initial; reserved=ZERO; orders={}; positions={}; ledger=[]; decisions=[]; trades=[]; equity=[]; marks={}

    def post(at, sid, kind, amount, **details):
        nonlocal cash
        amount=money(amount); cash=money(cash+amount)
        ledger.append(dict(at=at.isoformat(),id=sid,kind=kind,amount=str(amount),cash=str(cash),**details))

    def value():
        total=cash
        for key,p in positions.items():
            adapter=adapters[key]; mark, rate=marks[key]
            if adapter.margin_fraction == 1:
                total += p['qty']*mark*adapter.multiplier*rate
            else:
                total += p['collateral']+(mark-p['entry'])*p['qty']*adapter.multiplier*p['signal'].side*rate
        return money(total)

    def close(key,b,price,reason,ambiguous=False):
        p=positions.pop(key); s=p['signal']; adapter=adapters[key]; rate=adapter.rate(b.session)
        fill=costs.fill(price,-s.side); notional=p['qty']*fill*adapter.multiplier*rate
        fee=costs.fee(notional,-s.side)
        if adapter.margin_fraction == 1:
            proceeds=notional
        else:
            proceeds=p['collateral']+(fill-p['entry'])*p['qty']*adapter.multiplier*s.side*rate
        post(b.available_at,s.id,'EXIT',proceeds,reason=reason,price=str(fill),quantity=str(p['qty']),
             spread_impact=str(money(p['qty']*price*adapter.multiplier*rate*costs.spread_bps/20000)),
             slippage_impact=str(money(p['qty']*price*adapter.multiplier*rate*costs.slippage_bps/10000)))
        post(b.available_at,s.id,'FEE',-fee)
        pnl=money(proceeds-p['capital']-fee-p['entry_fee']+p['distributions']-p['financing'])
        entry_rate=p['entry_rate'] if adapter.margin_fraction==1 else rate
        execution_cost=money(((p['entry']-p['entry_mid'])*entry_rate+(price-fill)*rate)*p['qty']*adapter.multiplier*s.side)
        trades.append(dict(id=s.id,instrument=key,side=s.side,entry_session=p['entry_session'],exit_session=b.session,
                           strategy_profile_id=s.strategy_profile_id,strategy_profile_version=s.strategy_profile_version,
                           entry=str(p['entry']),exit=str(fill),quantity=str(p['qty']),held=p['held'],reason=reason,
                           ambiguous=ambiguous,net_pnl=str(pnl),fees=str(p['entry_fee']+fee),
                           financing=str(p['financing']),distributions=str(p['distributions']),execution_cost=str(execution_cost),
                           gross_pnl=str(money(pnl+fee+p['entry_fee']+p['financing']+execution_cost)),
                           favorable_daily_range_r_bound=str(p['mfe']),adverse_daily_range_r_bound=str(p['mae']),
                           excursion_basis='DAILY_RANGE_BOUNDS_EXIT_BAR_ORDER_UNKNOWN'))

    # Group equal timestamps so carried exits across all instruments precede entries.
    times = sorted({e[0] for e in events})
    for at in times:
        group=sorted((e for e in events if e[0]==at),key=lambda e:(e[1],e[2]))
        bars=[(key,b) for _,kind,key,b in group if kind==1]
        for key,b in bars:
            adapter=adapters[key]; rate=adapter.rate(b.session)
            marks[key]=(N(b.close),rate); history=histories[key]; history.append(b)
            action=action_map.get((key,b.session))
            if action and action.split!=1:
                # Rebase prior raw feature history to current share units. Input
                # manifest remains byte/semantically immutable.
                history[:-1]=[replace(old,**{field:N(getattr(old,field))/action.split for field in ('open','high','low','close')},
                                     activity=None if old.activity is None else N(old.activity)*action.split) for old in history[:-1]]
                for sid,order in tuple(orders.items()):
                    if order.instrument==key: orders[sid]=replace(order,stop=order.stop/action.split,
                        target_distance=None if order.target_distance is None else order.target_distance/action.split)
            if key not in positions: continue
            p=positions[key]; s=p['signal']; side=s.side; p['held']+=1
            if action:
                # Raw ex-action prices; adjust shares and frozen levels exactly once.
                p['qty']*=action.split
                for field in ('entry','entry_mid','stop','initial_r','best'): p[field]/=action.split
                if p['target'] is not None: p['target']/=action.split
                dividend=money(p['qty']*action.dividend*adapter.multiplier*rate*side)
                post(at,s.id,'DISTRIBUTION',dividend); p['distributions']+=dividend
            financing=money(adapter.financing(p,b.session,p['previous_session']))
            post(at,s.id,'FINANCING',-financing); p['financing']+=financing; p['previous_session']=b.session
            o,h,l,c=(N(getattr(b,k)) for k in ('open','high','low','close'))
            p['mfe']=max(p['mfe'],((h-p['entry']) if side==1 else (p['entry']-l))/p['initial_r'])
            p['mae']=max(p['mae'],((p['entry']-l) if side==1 else (h-p['entry']))/p['initial_r'])
            stop=p['stop']; target=p['target']
            hit_stop=l<=stop if side==1 else h>=stop
            hit_target=target is not None and (h>=target if side==1 else l<=target)
            gap_stop=o<=stop if side==1 else o>=stop
            gap_target=target is not None and (o>=target if side==1 else o<=target)
            if p['invalidation'] or gap_stop: close(key,b,o,'NEXT_OPEN_INVALIDATION' if p['invalidation'] else 'GAP_STOP',hit_stop and hit_target)
            elif gap_target: close(key,b,target,'GAP_TARGET_LIMIT')
            elif hit_stop: close(key,b,stop,'AMBIGUOUS_STOP_FIRST' if hit_target else 'STOP',hit_target)
            elif hit_target: close(key,b,target,'TARGET')
            elif s.exit_mode=='EMA21_CLOSE' and len(history)>=21 and ((c-ema_close(history,21))*side)<0: close(key,b,c,'EMA21_CLOSE')
            elif p['held']>=s.horizon: close(key,b,c,'HORIZON_CLOSE')
            elif s.trail!='NONE' and (p['armed'] or (c-p['entry'])*side>=p['initial_r']*s.trail_activation_r):
                p['armed']=True
                p['best']=max(p['best'],c) if side==1 else min(p['best'],c)
                a=atr(history,s.atr_period)
                if a is not None:
                    candidate=p['best']-side*s.trail_k*a if s.trail=='ATR' else (min(N(x.low) for x in history[-2:])-a/4 if side==1 else max(N(x.high) for x in history[-2:])+a/4)
                    p['stop']=max(stop,candidate) if side==1 else min(stop,candidate)
                    p['invalidation']=(c-p['stop'])*side<=0
                    decisions.append(dict(id=s.id,at=at.isoformat(),state='TRAIL_NEXT_SESSION',stop=str(p['stop'])))
        for key,b in bars:
            adapter=adapters[key]
            for sid,s in sorted(tuple(orders.items())):
                if s.instrument!=key or b.available_at<=s.decision_at: continue
                reserved-=s.max_notional; del orders[sid]
                reason=None; close_price=N(b.close); side=s.side
                if b.available_at>s.decision_at+timedelta(days=s.expiry_days): reason='EXPIRED'
                elif key in positions: reason='POSITION_EXISTS'
                elif side==-1 and not adapter.allow_short: reason='CASH_LONG_ONLY'
                elif (close_price-s.stop)*side<=0 or (N(b.low)<=s.stop if side==1 else N(b.high)>=s.stop): reason='INVALIDATED_BEFORE_CLOSE'
                rate=adapter.rate(b.session); fill=costs.fill(close_price,side); risk=(fill-s.stop)*side
                if risk<=0: reason='INVALID_GEOMETRY'
                if reason:
                    decisions.append(dict(id=sid,at=at.isoformat(),state=reason)); continue
                unit=fill*adapter.multiplier*rate*adapter.margin_fraction
                qty=min(s.risk_budget/(risk*adapter.multiplier*rate),s.max_notional/unit)
                qty=(qty/adapter.lot).to_integral_value(rounding=ROUND_FLOOR)*adapter.lot
                while qty>0 and money(qty*unit)+costs.fee(qty*fill*adapter.multiplier*rate,side)>min(s.max_notional,cash-reserved): qty-=adapter.lot
                if qty<=0:
                    decisions.append(dict(id=sid,at=at.isoformat(),state='NO_CAPITAL')); continue
                target_distance=s.target_distance
                if target_distance is not None and s.target_policy!='UNCHANGED':
                    # Cash-equity research only: solve for a gross target whose
                    # expected net P&L reaches the chosen initial-risk multiple.
                    if side!=1 or adapter.margin_fraction!=1 or adapter.multiplier!=1 or rate!=1:
                        raise ValueError('target economics currently requires long ZAR cash equity')
                    entry_fee=costs.fee(qty*fill)
                    requested=fill+target_distance
                    def net_at(target):
                        exit_fill=costs.fill(target,-1)
                        return (exit_fill-fill)*qty-entry_fee-costs.fee(qty*exit_fill,-1)
                    required=s.target_min_net_r*risk*qty
                    if net_at(requested)<required:
                        if s.target_policy=='REJECT':
                            decisions.append(dict(id=sid,at=at.isoformat(),state='TARGET_ECONOMICS_REJECTED',
                                entry=str(fill),stop=str(s.stop),target=str(requested),quantity=str(qty),
                                gross_target_r=str(target_distance/risk),estimated_net_target_pnl=str(money(net_at(requested))),
                                estimated_net_target_r=str(net_at(requested)/(risk*qty)),fee_basis=costs.basis));continue
                        # Bisection includes minimum and proportional fees.
                        lower=requested;upper=max(fill+risk,requested)*2
                        for _ in range(64):
                            if net_at(upper)>=required:break
                            upper*=2
                        else:raise ValueError('target cannot cover requested net reward with these costs')
                        for _ in range(64):
                            midpoint=(lower+upper)/2
                            if net_at(midpoint)<required:lower=midpoint
                            else:upper=midpoint
                        target_distance=upper-fill
                capital=money(qty*unit); fee=costs.fee(qty*fill*adapter.multiplier*rate,side)
                post(at,sid,'ENTRY',-capital,price=str(fill),quantity=str(qty),
                     spread_impact=str(money(qty*close_price*adapter.multiplier*rate*costs.spread_bps/20000)),
                     slippage_impact=str(money(qty*close_price*adapter.multiplier*rate*costs.slippage_bps/10000))); post(at,sid,'FEE',-fee)
                positions[key]=dict(signal=s,qty=qty,entry=fill,entry_mid=close_price,entry_rate=rate,stop=s.stop,initial_r=risk,
                    target=(fill+side*target_distance if target_distance is not None else
                            None if s.target_r is None else fill+side*s.target_r*risk),
                    capital=capital,collateral=capital,entry_fee=fee,held=0,entry_session=b.session,
                    previous_session=b.session,best=fill,armed=False,invalidation=False,financing=ZERO,distributions=ZERO,mfe=ZERO,mae=ZERO)
                economics_distance=target_distance if target_distance is not None else (s.target_r*risk if s.target_r is not None else None)
                if economics_distance is not None:
                    target_price=fill+side*economics_distance
                    projected_exit=costs.fill(target_price,-side)
                    projected_net=(projected_exit-fill)*qty*side-fee-costs.fee(qty*projected_exit,-side)
                    decisions.append(dict(id=sid,at=at.isoformat(),state='TARGET_ECONOMICS',entry=str(fill),stop=str(s.stop),
                        target=str(target_price),quantity=str(qty),gross_target_r=str(economics_distance/risk),
                        estimated_net_target_pnl=str(money(projected_net)),estimated_net_target_r=str(projected_net/(risk*qty)),
                        fee_basis=costs.basis,target_policy=s.target_policy))
                decisions.append(dict(id=sid,at=at.isoformat(),state='FILLED'))
        for _,kind,_,s in group:
            if kind!=2: continue
            if s.max_notional>cash-reserved:
                decisions.append(dict(id=s.id,at=at.isoformat(),state='CAPITAL_REJECTED')); continue
            reserved+=s.max_notional; orders[s.id]=s
            decisions.append(dict(id=s.id,at=at.isoformat(),state='RESERVED'))
        expired=[sid for sid,s in orders.items() if at>s.decision_at+timedelta(days=s.expiry_days)]
        for sid in expired:
            reserved-=orders[sid].max_notional; del orders[sid]
            decisions.append(dict(id=sid,at=at.isoformat(),state='EXPIRED'))
        equity.append(dict(at=at.isoformat(),cash=str(cash),reserved=str(reserved),equity=str(value()),positions=len(positions)))
    for sid,s in tuple(orders.items()):
        if now>s.decision_at+timedelta(days=s.expiry_days):
            reserved-=s.max_notional; del orders[sid]
            decisions.append(dict(id=sid,at=now.isoformat(),state='EXPIRED'))
    result=dict(engine_version=VERSION,execution_enabled=False,grade='SYNTHETIC' if all(m.grade=='SYNTHETIC' for m in manifests) else 'ASSUMPTION_LIMITED',
                dataset_hashes={m.instrument:m.sha256 for m in manifests},
                config_hash=configuration_hash(dict(signals=[asdict(s) for s in signals],costs=asdict(costs),actions=[asdict(a) for a in actions],
                    initial_cash=str(initial),account_currency=account_currency,adapters={k:a.configuration() for k,a in adapters.items()})),
                ledger=ledger,decisions=decisions,trades=trades,equity=equity,cash=str(cash),reserved=str(reserved),
                pending_orders=sorted(orders),open_positions=sorted(positions),cost_basis=costs.basis,
                limitations=['FULL_FILL_ASSUMPTION','CLOSE_PROXY_NOT_BROKER_FILL','DAILY_INTRABAR_PATH_UNKNOWN'])
    result['semantic_hash']=configuration_hash(result)
    return result
