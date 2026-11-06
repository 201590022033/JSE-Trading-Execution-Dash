"""Illustrative OST cash-share round-trip cost and break-even estimate."""
from decimal import Decimal, ROUND_HALF_UP
from domain.backtest.acceptance import published_share_fee
from domain.backtest.data import number


def estimate(quantity, entry, exit_price, brokerage_rate='0.005', spread_bps='0'):
    qty=number(quantity);buy=number(entry);sell=number(exit_price);rate=number(brokerage_rate);spread=number(spread_bps)
    if qty<=0 or qty!=qty.to_integral_value() or qty>100000000:raise ValueError('positive whole-share quantity required')
    if min(buy,sell)<=0 or max(buy,sell)>10000000:raise ValueError('positive prices in rand required')
    if rate not in (Decimal('.0025'),Decimal('.005')) or spread<0 or spread>1000:raise ValueError('unsupported fee scenario or spread')
    q=Decimal('.01')
    def round_money(x):return x.quantize(q,rounding=ROUND_HALF_UP)
    buy_fill=buy*(1+spread/20000); sell_fill=sell*(1-spread/20000)
    buy_value=buy_fill*qty;sell_value=sell_fill*qty
    entry_fee=published_share_fee(buy_value,1,brokerage_rate=rate)
    exit_fee=published_share_fee(sell_value,-1,brokerage_rate=rate)
    fee=lambda x:number(x['total'])
    gross=(sell-buy)*qty;net=sell_value-buy_value-fee(entry_fee)-fee(exit_fee)
    def net_for(mid):
        proceeds=mid*(1-spread/20000)*qty
        return proceeds-buy_value-fee(entry_fee)-fee(published_share_fee(proceeds,-1,brokerage_rate=rate))
    lower=buy;upper=max(buy*2,Decimal(1))
    for _ in range(50):
        if net_for(upper)>=0:break
        upper*=2
    else:raise ValueError('break-even unavailable')
    for _ in range(64):
        mid=(lower+upper)/2
        if net_for(mid)<0:lower=mid
        else:upper=mid
    return {'quantity':str(qty),'entry_price':str(buy),'exit_price':str(sell),'buy_fill':str(buy_fill),
      'sell_fill':str(sell_fill),'buy_notional':str(round_money(buy_value)),'sell_notional':str(round_money(sell_value)),
      'entry_costs':entry_fee,'exit_costs':exit_fee,'gross_profit':str(round_money(gross)),
      'estimated_costs_including_spread':str(round_money(gross-net)),'net_profit':str(round_money(net)),
      'break_even_price':str(upper.quantize(q,rounding='ROUND_CEILING')),
      'brokerage_rate':str(rate),'spread_bps':str(spread),'live_execution':False,
      'basis':'ILLUSTRATIVE_PUBLISHED_SCHEDULE_NOT_ACCOUNT_VERIFIED',
      'limitations':['CASH_SHARES_ONLY_NOT_CFD_OR_ETF','BROKER_RATE_AND_MINIMUM_REQUIRE_ACCOUNT_CONFIRMATION',
       'VAT_AND_ROUNDING_ASSUMED','NO_ACCOUNT_OR_FINANCING_FEES','NO_CAPITAL_GAINS_TAX']}


def closed_trade_sensitivity(trades, brokerage_rate='0.005'):
    """Reprice fees on saved fills, without pretending to rerun portfolio sizing."""
    total=Decimal(0);fees=Decimal(0);prior=Decimal(0)
    for t in trades:
        qty=number(t['quantity']);entry=number(t['entry']);exit_price=number(t['exit'])
        if int(t.get('side',1))!=1 or qty<=0:raise ValueError('long cash shares required')
        buy_fee=number(published_share_fee(entry*qty,1,brokerage_rate=brokerage_rate)['total'])
        sell_fee=number(published_share_fee(exit_price*qty,-1,brokerage_rate=brokerage_rate)['total'])
        fees+=buy_fee+sell_fee;total+=(exit_price-entry)*qty-buy_fee-sell_fee
        prior+=number(t['net_pnl'])
    return {'trades':len(trades),'original_net':str(prior.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)),
            'estimated_fees':str(fees.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)),
            'estimated_net':str(total.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)),
            'basis':'SAME_FILLS_REPRICE_FEES_ONLY_NOT_PORTFOLIO_REPLAY'}
