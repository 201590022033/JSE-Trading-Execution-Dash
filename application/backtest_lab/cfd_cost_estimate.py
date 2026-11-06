"""CFD calculator: observed symmetric fixed fees; explicit extra costs."""
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING, ROUND_FLOOR
from domain.backtest.data import number


def estimate_cfd(quantity, entry, exit_price, side='long', financing='0', extra_cost='0', fee_per_leg='57.50'):
    qty=number(quantity);entry=number(entry);exit_price=number(exit_price)
    financing=number(financing);extra_cost=number(extra_cost);fee=number(fee_per_leg)
    if qty<=0 or qty!=qty.to_integral_value() or qty>100000000:raise ValueError('positive whole contracts required')
    if min(entry,exit_price)<=0 or max(entry,exit_price)>10000000:raise ValueError('positive prices required')
    if side not in ('long','short') or min(extra_cost,fee)<0 or max(abs(financing),extra_cost,fee)>10000000:raise ValueError('invalid assumptions')
    direction=1 if side=='long' else -1
    gross=(exit_price-entry)*qty*direction
    costs=fee*2+financing+extra_cost
    net=gross-costs
    break_even=entry+direction*costs/qty
    rounding=ROUND_CEILING if side=='long' else ROUND_FLOOR
    cents=Decimal('.01')
    def money(x):return str(x.quantize(cents,rounding=ROUND_HALF_UP))
    return {'quantity':str(qty),'side':side,'entry':str(entry),'exit':str(exit_price),
            'gross_pnl':money(gross),'entry_brokerage':money(fee),'exit_brokerage':money(fee),
            'net_financing_cost':money(financing),'extra_cost':money(extra_cost),'total_costs':money(costs),
            'net_pnl':money(net),'break_even_exit':str(break_even.quantize(cents,rounding=rounding)) if break_even>0 else None,
            'live_execution':False,'basis':'OBSERVED_ONE_CFD_ENTRY_USER_CONFIRMED_SYMMETRIC_EXIT',
            'limitations':['ONE_OBSERVED_ENTRY_NOT_UNIVERSAL_ACCOUNT_TARIFF',
              'ONE_SHARE_PER_CONTRACT_ASSUMED','FINANCING_AND_EXTRA_COST_USER_SUPPLIED',
              'EXECUTED_PRICES_MUST_INCLUDE_ANY_SPREAD_NOT_ADDED_AUTOMATICALLY','NO_ACCOUNT_FEES_OR_TAX_ON_GAINS']}
