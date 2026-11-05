import unittest
from unittest.mock import patch
from scripts.audit_backtest_sectors import audit


class SectorAuditTests(unittest.TestCase):
    @patch('scripts.audit_backtest_sectors.classifications')
    @patch('scripts.audit_backtest_sectors._read')
    def test_groups_closed_trades_and_preserves_unclassified(self, read, catalog):
        catalog.return_value={'instruments':{'BTI':{'sector':'Consumer'},'XYZ':{'sector':'Unclassified'}}}
        read.return_value={'meta':{'grade':'ASSUMPTION_LIMITED'},'bars':{'BTI':[],'XYZ':[]},
            'strategies':[{'id':'box','name':'Box','run':{'signals':[{'inst':'BTI'}], 'trades':[
                {'instrument':'BTI','net_pnl':'100.20'}, {'instrument':'BTI','net_pnl':'-20.10'},
                {'instrument':'XYZ','net_pnl':'5.00'}]}}]}
        text=audit('.', 'a'*64)
        self.assertIn('| Consumer | BTI | 0; R0.00 | 0; R0.00 | 2; R80.10 |',text)
        self.assertIn('| Unclassified | XYZ |',text)
        self.assertIn('| Box | 1 | 2 | 1 | R80.10 |',text)
        self.assertIn('Unclassified in research taxonomy (1 of 2): XYZ',text)


if __name__=='__main__': unittest.main()
