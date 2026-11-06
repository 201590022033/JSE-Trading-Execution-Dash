import unittest
from flask import Flask
from application.backtest_lab.blueprint import create_backtest_lab_blueprint
from application.backtest_lab.cfd_cost_estimate import estimate_cfd

class CfdCostTests(unittest.TestCase):
    def test_absa_symmetric_brokerage_and_financing(self):
        e=estimate_cfd(3,'220.75','230.12',financing='6.88')
        self.assertEqual(e['gross_pnl'],'28.11')
        self.assertEqual(e['entry_brokerage'],'57.50');self.assertEqual(e['exit_brokerage'],'57.50')
        self.assertEqual(e['net_pnl'],'-93.77');self.assertEqual(e['break_even_exit'],'261.38')

    def test_short_and_validation(self):
        e=estimate_cfd(10,100,90,side='short',fee_per_leg=5)
        self.assertEqual(e['net_pnl'],'90.00');self.assertEqual(e['break_even_exit'],'99.00')
        with self.assertRaises(ValueError):estimate_cfd('1.5',100,101)
        with self.assertRaises(ValueError):estimate_cfd(1,100,101,extra_cost=-1)

    def test_api_no_store_and_no_execution(self):
        app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint())
        c=app.test_client();r=c.get('/api/v1/backtest-lab/cfd-cost-estimate?quantity=3&entry=220.75&exit=230.12')
        self.assertEqual(r.status_code,200);self.assertEqual(r.headers['Cache-Control'],'no-store');self.assertFalse(r.json['live_execution'])
        self.assertEqual(c.get('/api/v1/backtest-lab/cfd-cost-estimate?quantity=0&entry=1&exit=1').status_code,400)
