import unittest
from decimal import Decimal
from flask import Flask
from application.backtest_lab.blueprint import create_backtest_lab_blueprint
from application.backtest_lab.share_cost_estimate import estimate,closed_trade_sensitivity

class ShareCostTests(unittest.TestCase):
    def test_minimum_fees_buy_tax_and_break_even(self):
        e=estimate(100,100,105)
        self.assertEqual(e['entry_costs']['components']['brokerage'],'110.00')
        self.assertEqual(e['entry_costs']['components']['purchase_tax'],'25.00')
        self.assertEqual(e['exit_costs']['components']['purchase_tax'],'0.00')
        self.assertGreater(Decimal(e['gross_profit']),Decimal(e['net_profit']))
        self.assertGreater(Decimal(e['break_even_price']),Decimal('100'))
        b=estimate(100,100,e['break_even_price'])
        self.assertGreaterEqual(Decimal(b['net_profit']),0)

    def test_spread_reduces_net_and_bad_product_values_reject(self):
        self.assertLess(Decimal(estimate(100,100,105,spread_bps=30)['net_profit']),Decimal(estimate(100,100,105)['net_profit']))
        with self.assertRaises(ValueError):estimate('1.5',100,105)
        with self.assertRaises(ValueError):estimate(100,100,105,brokerage_rate='0.1')

    def test_http_is_read_only_and_no_store(self):
        app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint())
        client=app.test_client();r=client.get('/api/v1/backtest-lab/share-cost-estimate?quantity=100&entry=100&exit=105')
        self.assertEqual(r.status_code,200);self.assertEqual(r.headers['Cache-Control'],'no-store');self.assertFalse(r.json['live_execution'])
        self.assertEqual(client.get('/api/v1/backtest-lab/share-cost-estimate?quantity=0&entry=100&exit=105').status_code,400)

    def test_saved_fill_sensitivity_replaces_fees_without_double_counting_spread(self):
        t={'quantity':'100','entry':'100','exit':'105','net_pnl':'490','side':1}
        e=estimate(100,100,105);s=closed_trade_sensitivity([t])
        self.assertEqual(s['estimated_net'],e['net_profit'])
        self.assertEqual(s['original_net'],'490.00')
