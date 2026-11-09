import unittest
from flask import Flask
from application.strategy_radar.trade_plan import build_trade_plan
from application.strategy_radar.api import create_radar_blueprint


def cash(**changes):
    return dict(dict(product='CASH_SHARE',direction='LONG',price_unit='ZAR',entry='100',quantity='100',stop_trigger='95',target='110'),**changes)


class TradePlanTests(unittest.TestCase):
 def test_cash_fees_risk_and_cents(self):
    result=build_trade_plan(cash())
    assert result['target_estimate']['gross_profit']=='1000.00'
    assert result['target_estimate']['net_profit']=='707.46'
    assert result['target_estimate']['break_even_price']=='102.93'
    assert result['stop_estimate']['estimated_loss']=='792.52'
    assert result['cash_required']=='10158.76'
    cents=build_trade_plan(cash(price_unit='ZAR_CENTS',entry='10000',stop_trigger='9500',target='11000'))
    assert cents['target_estimate']==result['target_estimate']


 def test_separate_stop_and_trailing_validation(self):
    result=build_trade_plan(cash(stop_limit='94',trailing_mode='PRICE',trailing_distance='250',trailing_distance_unit='ZAR_CENTS'))
    assert result['prices_zar']['stop_limit']=='94'
    assert result['trailing']['distance']=='2.5'
    assert build_trade_plan(cash(trailing_mode='PERCENT',trailing_distance='2.5'))['trailing']['unit']=='PERCENT'
    with self.assertRaises(ValueError): build_trade_plan(cash(stop_limit='96'))
    with self.assertRaises(ValueError): build_trade_plan(cash(quantity='1.5'))
    with self.assertRaises(ValueError): build_trade_plan(cash(trailing_mode='PERCENT',trailing_distance='100'))


 def test_cfd_short_fees_and_input_gaps(self):
    payload=dict(product='CFD',direction='SHORT',price_unit='ZAR',entry='100',quantity='10',stop_trigger='105',target='90',contract_size='1',financing='0',extra_cost='0',margin_rate='0.2')
    result=build_trade_plan(payload)
    assert result['target_estimate']['gross_pnl']=='100.00'
    assert result['target_estimate']['net_pnl']=='-15.00'
    assert result['target_estimate']['break_even_exit']=='88.50'
    assert result['stop_estimate']['estimated_loss']=='165.00'
    assert result['margin_required']=='200.00'
    payload['financing']=''
    assert build_trade_plan(payload)['target_estimate'] is None
    payload.update(direction='LONG',target='120',stop_trigger='95',financing='-20')
    assert build_trade_plan(payload)['target_estimate']['break_even_exit']=='109.50'


 def test_unsupported_products_are_explicit(self):
    for product in ('ETF','SSF','OPTION','FOREX'):
        plan=build_trade_plan({'product':product})
        assert plan['missing'] and plan['target_estimate'] is None


 def test_api_unverified_fields_never_copy_and_rejects_cross_origin(self):
    app=Flask(__name__); app.register_blueprint(create_radar_blueprint(lambda: None)); client=app.test_client()
    result=client.post('/api/v1/strategy-radar/trade-plan',json=cash())
    assert result.status_code==200
    assert all(item['copy_value'] is None and item['state']=='UNAVAILABLE' for item in result.json['ost_fields'].values())
    assert client.post('/api/v1/strategy-radar/trade-plan',json=cash(),headers={'Origin':'https://example.com'}).status_code==403
