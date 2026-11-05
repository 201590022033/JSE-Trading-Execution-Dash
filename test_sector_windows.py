import unittest
from application.backtest_lab.sector_windows import analyse
from scripts.sector_swing_exploration import windows, VARIANTS
from application.backtest_lab.sector_hypothesis import prepare, prompt, validate

class SectorWindowTests(unittest.TestCase):
    def test_window_selection_does_not_use_later_outcomes(self):
        from datetime import date, timedelta
        days=[(date(2024,1,1)+timedelta(days=i)).isoformat() for i in range(100)]
        def strategy(name, train, later):
            return {'id':name,'name':name,'run':{'signals':[], 'trades':[
                {'instrument':'BTI','entry_session':days[20],'exit_session':days[21],'net_pnl':str(train)},
                {'instrument':'BTI','entry_session':days[90],'exit_session':days[91],'net_pnl':str(later)},
                {'instrument':'BTI','entry_session':days[59],'exit_session':days[60],'net_pnl':'999'}]}}
        run={'bars':{'BTI':[[d,1,1,1,1] for d in days]}, 'strategies':[strategy('box',10,-50),strategy('swing',1,100)]}
        result=analyse(run); row=result['instruments'][0]
        self.assertEqual(row['training_lead'],'box')
        box=row['strategies'][0]['windows']
        self.assertEqual(box['training']['net'],10)
        self.assertEqual(box['holdout']['net'],-50)
        self.assertEqual(box['training']['boundary_crossing_excluded'],1)
        context, report=prepare(run, 'Consumer')
        text=prompt(context)
        self.assertNotIn('-50', text)
        self.assertNotIn('holdout', text)
        self.assertEqual(validate('{"strategy_id":"box","rationale":"test"}',context['strategy_ids'])['strategy_id'],'box')
        with self.assertRaises(ValueError): validate('{"strategy_id":"unknown","rationale":"test"}',context['strategy_ids'])
    def test_variants_are_fixed_and_include_relaxed_rules(self):
        self.assertEqual(len(VARIANTS),3)
        self.assertEqual(VARIANTS[1][1]['volume_min'],0.8)
        self.assertEqual(VARIANTS[2][2],'CLOSE_ABOVE_EMA50')
        with self.assertRaises(ValueError): windows(['x']*149)
