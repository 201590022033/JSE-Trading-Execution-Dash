"""Product-aware manual plan estimates; research only, never submits orders."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from application.backtest_lab.share_cost_estimate import estimate as estimate_share
from application.backtest_lab.cfd_cost_estimate import estimate_cfd

SUPPORTED = {'CASH_SHARE', 'CFD'}
PRODUCT_GAPS = {
    'ETF':['ETF-specific tariff, tax and instrument terms'],
    'SSF':['contract multiplier, expiry, margin and fee terms'],
    'OPTION':['contract multiplier, exercise/expiry and premium/fee terms'],
    'FOREX':['pair, pip value, contract size, currency conversion, financing and margin terms'],
}


def _num(raw, name, *, nonnegative=False, positive=False):
    if raw is None or isinstance(raw,bool):
        raise ValueError(f'{name} is required')
    try:
        value=Decimal(str(raw))
    except (InvalidOperation,ValueError):
        raise ValueError(f'{name} must be a finite decimal') from None
    if not value.is_finite() or (positive and value<=0) or (nonnegative and value<0):
        raise ValueError(f'{name} has invalid value')
    return value


def _money(value):
    return str(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP))


def _price(payload, field):
    raw=payload.get(field)
    if raw is None or raw=='': return None
    value=_num(raw,field,positive=True)
    unit=payload.get(field+'_unit',payload.get('price_unit'))
    if unit not in ('ZAR','ZAR_CENTS'):
        raise ValueError(f'{field} needs explicit ZAR or ZAR_CENTS unit')
    return value/Decimal(100) if unit=='ZAR_CENTS' else value


def build_trade_plan(payload):
    """Return an explicit partial or calculated manual decision plan.

    Inputs: product CASH_SHARE/CFD/ETF/SSF/OPTION/FOREX, direction LONG/SHORT,
    price_unit ZAR/ZAR_CENTS (optional per-field overrides via `<field>_unit`),
    entry, quantity, stop_trigger, optional stop_limit and target. Optional
    trailing uses `trailing_mode` NONE/PRICE/PERCENT and `trailing_distance`,
    price unit via `trailing_distance_unit` if PRICE. CFD needs explicit
    `contract_size=1`, `financing` and `extra_cost`; fee_per_leg defaults to
    the separately documented R57.50 observed scenario, not an account quote.
    Cash uses 0.5% published scenario and zero spread unless specified. Prices
    supplied for CFD are executable fill assumptions; no spread is added.
    """
    if not isinstance(payload,dict): raise ValueError('object required')
    product=str(payload.get('product') or '').upper()
    if product not in SUPPORTED|set(PRODUCT_GAPS): raise ValueError('supported product identifier required')
    direction=str(payload.get('direction') or 'LONG').upper()
    if direction not in ('LONG','SHORT'): raise ValueError('direction must be LONG or SHORT')
    base={'product':product, 'direction':direction,'live_execution':False,'research_only':True,
          'state':'NEEDS_INPUT','missing':[], 'prices_zar':{},'quantity':None,
          'trailing':None,'target_estimate':None,'stop_estimate':None,'cash_required':None,
          'margin_required':None,'holding_horizon':payload.get('holding_horizon'),
          'assumptions':[], 'limitations':[]}
    if product in PRODUCT_GAPS:
        base['missing']=PRODUCT_GAPS[product]
        base['limitations']=['PRODUCT_CALCULATION_NOT_IMPLEMENTED','NO_ASSUMED_BROKER_FIELD_UNITS']
        return base
    if product=='CASH_SHARE' and direction=='SHORT':
        base['missing']=['verified short cash-share contract and borrowing terms']
        base['limitations']=['LONG_CASH_SHARES_ONLY']
        return base
    values={k:_price(payload,k) for k in ('entry','stop_trigger','stop_limit','target')}
    base['prices_zar']={k:str(v) if v is not None else None for k,v in values.items()}
    qty_raw=payload.get('quantity')
    qty=None if qty_raw is None or qty_raw=='' else _num(qty_raw,'quantity',positive=True)
    if qty is not None and (qty!=qty.to_integral_value() or qty>100000000): raise ValueError('whole positive quantity required')
    base['quantity']=str(qty) if qty is not None else None
    entry,stop,limit,target=(values[k] for k in ('entry','stop_trigger','stop_limit','target'))
    for key,value in (('entry',entry),('quantity',qty),('stop_trigger',stop),('target',target)):
        if value is None: base['missing'].append(key)
    if entry is not None:
        if stop is not None and ((direction=='LONG' and stop>=entry) or (direction=='SHORT' and stop<=entry)):
            raise ValueError('stop trigger must be on the risk side of entry')
        if target is not None and ((direction=='LONG' and target<=entry) or (direction=='SHORT' and target>=entry)):
            raise ValueError('target must be on the profit side of entry')
    if limit is not None and stop is None: raise ValueError('stop limit requires a separate stop trigger')
    if limit is not None and ((direction=='LONG' and limit>stop) or (direction=='SHORT' and limit<stop)):
        raise ValueError('stop limit is on the wrong side of trigger')
    trail=str(payload.get('trailing_mode') or 'NONE').upper()
    if trail not in ('NONE','PRICE','PERCENT'): raise ValueError('unsupported trailing mode')
    if trail=='NONE':
        base['trailing']={'mode':'NONE','distance':None,'unit':None}
    else:
        raw=payload.get('trailing_distance')
        if raw is None or raw=='':
            base['missing'].append('trailing_distance')
            base['trailing']={'mode':trail,'distance':None,'unit':'PERCENT' if trail=='PERCENT' else 'ZAR'}
        elif trail=='PERCENT':
            value=_num(raw,'trailing_distance',positive=True)
            if value>=100: raise ValueError('trailing percent must be less than 100')
            base['trailing']={'mode':trail,'distance':str(value),'unit':'PERCENT'}
        else:
            value=_price({**payload,'trailing_distance':raw},'trailing_distance')
            base['trailing']={'mode':trail,'distance':str(value),'unit':'ZAR'}
    if product=='CASH_SHARE':
        rate=str(payload.get('brokerage_rate','0.005'))
        spread=str(payload.get('spread_bps','0'))
        base['assumptions']=[f'Illustrative cash-share fee scenario: {rate} brokerage with R110 minimum before VAT; current account tariff unverified',
                             'Spread/slippage bps is a separate user assumption; default zero',
                             'Stop-trigger fill assumes execution at trigger; gaps and stop-limit non-fill can increase loss']
        base['limitations']=['CASH_SHARES_ONLY','CURRENT_ACCOUNT_TARIFF_UNVERIFIED','NO_CAPITAL_GAINS_TAX','NO_ACCOUNT_FEES']
        if entry is not None and qty is not None:
            if target is not None:
                target_result=estimate_share(qty,entry,target,rate,spread)
                base['target_estimate']=target_result
                base['cash_required']=_money(Decimal(target_result['buy_notional'])+Decimal(target_result['entry_costs']['total']))
            if stop is not None:
                stop_result=estimate_share(qty,entry,stop,rate,spread)
                base['stop_estimate']={'gross_pnl':stop_result['gross_profit'],'net_pnl':stop_result['net_profit'],
                    'estimated_loss':_money(max(Decimal(0),-Decimal(stop_result['net_profit']))),
                    'entry_costs':stop_result['entry_costs'],'exit_costs':stop_result['exit_costs'],
                    'fill_assumption':'STOP_TRIGGER_NOT_GUARANTEED'}
                if base['cash_required'] is None:
                    base['cash_required']=_money(Decimal(stop_result['buy_notional'])+Decimal(stop_result['entry_costs']['total']))
    else:
        size=payload.get('contract_size')
        if size is None or size=='':base['missing'].append('contract_size')
        elif _num(size,'contract_size',positive=True)!=1:
            base['missing'].append('supported one-share-per-contract CFD terms')
        for item in ('financing','extra_cost'):
            if payload.get(item) is None or payload.get(item)=='':base['missing'].append(item)
        fee=_num(payload.get('fee_per_leg','57.50'),'fee_per_leg',nonnegative=True)
        financing=_num(payload['financing'],'financing') if payload.get('financing') not in (None,'') else None
        extra=_num(payload['extra_cost'],'extra_cost',nonnegative=True) if payload.get('extra_cost') not in (None,'') else None
        ready=size not in (None,'') and _num(size,'contract_size',positive=True)==1 and financing is not None and extra is not None
        base['assumptions']=['One share per CFD contract when explicitly confirmed',
                             f'Symmetric CFD brokerage assumption R{fee} per leg; R57.50 is an observed scenario, not a verified current tariff',
                             'Entry and exit are assumed executable fills; spread is included in those fills, never added again',
                             'Stop-trigger fill assumes execution at trigger; gaps and stop-limit non-fill can increase loss']
        base['limitations']=['CFD_FEES_AND_ACCOUNT_TERMS_UNVERIFIED','FINANCING_AND_EXTRA_COST_USER_SUPPLIED','NO_TAX_ON_GAINS']
        if ready and entry is not None and qty is not None:
            side=direction.lower()
            if target is not None: base['target_estimate']=estimate_cfd(qty,entry,target,side,financing,extra,fee)
            if stop is not None:
                estimate=estimate_cfd(qty,entry,stop,side,financing,extra,fee)
                base['stop_estimate']={**estimate,'estimated_loss':_money(max(Decimal(0),-Decimal(estimate['net_pnl']))),
                                       'fill_assumption':'STOP_TRIGGER_NOT_GUARANTEED'}
            margin=payload.get('margin_rate')
            if margin not in (None,''):
                rate=_num(margin,'margin_rate',positive=True)
                if rate>1: raise ValueError('margin_rate must be at most 1')
                base['margin_required']=_money(qty*entry*rate)
                base['assumptions'].append('Margin uses supplied fraction of entry notional, excludes fees and account buffers')
    base['state']='COMPLETE' if not base['missing'] else 'NEEDS_INPUT'
    return base
