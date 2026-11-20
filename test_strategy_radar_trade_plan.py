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


class SizeSuggestionTests(unittest.TestCase):
    def test_long_share_and_cents_use_costs_at_suggested_quantity(self):
        plan = build_trade_plan(cash(risk_budget='500', quantity='8'))
        suggestion = plan['size_suggestion']
        self.assertEqual(plan['quantity'], '8')
        self.assertEqual(suggestion['quantity'], '100')
        self.assertEqual(suggestion['quantity_unit'], 'shares')
        self.assertEqual(suggestion['estimated_costs_zar'], '292.52')
        self.assertEqual(suggestion['estimated_loss_zar'], '792.52')
        cents = build_trade_plan(cash(price_unit='ZAR_CENTS', entry='10000',
                                      stop_trigger='9500', target='11000', risk_budget='500'))
        self.assertEqual(cents['size_suggestion'], suggestion)

    def test_long_and_short_cfd_use_same_absolute_risk(self):
        inputs = dict(product='CFD', price_unit='ZAR', entry='100', contract_size='1',
                      financing='10', extra_cost='2', risk_budget='50')
        for direction, stop in (('LONG', '95'), ('SHORT', '105')):
            with self.subTest(direction=direction):
                plan = build_trade_plan(dict(inputs, direction=direction, stop_trigger=stop))
                suggestion = plan['size_suggestion']
                self.assertIsNone(plan['quantity'])
                self.assertEqual(suggestion['quantity'], '10')
                self.assertEqual(suggestion['quantity_unit'], 'contracts')
                self.assertEqual(suggestion['estimated_costs_zar'], '127.00')
                self.assertEqual(suggestion['estimated_loss_zar'], '177.00')

    def test_non_risk_side_stops_leave_target_estimates_available(self):
        cases = (
            (cash(stop_trigger='105'), 'Stop is above entry for a long.'),
            (cash(stop_trigger='100'), 'Stop equals entry. Enter a different stop price.'),
            (cash(product='CFD', direction='SHORT', stop_trigger='95', target='90',
                  contract_size='1', financing='0', extra_cost='0'),
             'Stop is below entry for a short.'),
        )
        for payload, message in cases:
            with self.subTest(message=message):
                plan = build_trade_plan(dict(payload, risk_budget='500'))
                self.assertEqual(plan['size_suggestion_message'], message)
                self.assertIsNone(plan.get('size_suggestion'))
                self.assertIsNone(plan['stop_estimate'])
                self.assertIsNotNone(plan['target_estimate'])

    def test_cap_and_small_budgets(self):
        uncapped = build_trade_plan(cash(risk_budget='504.99'))
        self.assertEqual(uncapped['size_suggestion']['quantity'], '100')
        plan = build_trade_plan(cash(risk_budget='504.99', notional_cap='2599'))
        self.assertEqual(plan['size_suggestion']['quantity'], '25')
        self.assertTrue(plan['size_suggestion']['notional_cap_applied'])
        for budget, cap, expected in (
            ('4.99', '', 'The risk budget is too small for this stop distance.'),
            ('500', '99', 'The notional cap is too small for one unit at this entry price.'),
        ):
            plan = build_trade_plan(cash(risk_budget=budget, notional_cap=cap))
            self.assertIsNone(plan.get('size_suggestion'))
            self.assertEqual(plan['size_suggestion_message'], expected)
            self.assertIsNotNone(plan['target_estimate'])

    def test_api_missing_inputs_and_explicit_manual_quantity(self):
        app = Flask(__name__)
        app.register_blueprint(create_radar_blueprint(lambda: None))
        client = app.test_client()
        endpoint = '/api/v1/strategy-radar/trade-plan'
        incomplete = client.post(endpoint, json=cash(stop_trigger='', risk_budget=''))
        self.assertEqual(incomplete.status_code, 200)
        self.assertIn('stop price and risk budget', incomplete.json['size_suggestion_message'])
        result = client.post(endpoint, json=cash(risk_budget='500', quantity=''))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['size_suggestion']['quantity'], '100')
        self.assertIsNone(result.json['quantity'])
        self.assertIsNone(result.json['ost_fields']['quantity']['copy_value'])

    def test_cash_short_and_unconfirmed_cfd_contract_have_no_suggestion(self):
        short_share = build_trade_plan(cash(direction='SHORT', risk_budget='500'))
        self.assertIsNone(short_share.get('size_suggestion'))
        cfd = cash(product='CFD', contract_size='', risk_budget='500')
        pending = build_trade_plan(cfd)
        self.assertIsNone(pending.get('size_suggestion'))
        self.assertIn('Confirm', pending['size_suggestion_message'])
        pending_costs = build_trade_plan(dict(cfd, contract_size='1'))
        self.assertEqual(pending_costs['size_suggestion']['quantity'], '100')
        self.assertIsNone(pending_costs['size_suggestion']['estimated_loss_zar'])
