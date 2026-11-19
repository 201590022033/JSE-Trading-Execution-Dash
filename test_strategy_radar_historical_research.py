import unittest

from application.strategy_radar.historical_research import historical_research


class HistoricalResearchTests(unittest.TestCase):
    def test_sasol_preserves_original_profiles_samples_and_admission(self):
        studies = historical_research('SASOL')
        self.assertEqual(studies['HR7']['rows'][0]['sample_count'], 2685)
        self.assertEqual({row['horizon'] for row in studies['HR8']['rows']}, {'5 sessions'})
        self.assertEqual(studies['HR9']['rows'][0]['version'], 'adaptive-technical-ensemble-v2')
        self.assertEqual(studies['HR10']['rows'][0]['result'], 'REJECT')
        self.assertEqual(studies['HR11']['rows'], [{
            'profile': 'energy_sasol', 'sample_count': 0, 'contract': 'SOL_CASH',
            'horizon': 'intraday_30m', 'result': 'INSUFFICIENT_EVIDENCE',
        }])

    def test_missing_share_does_not_inherit_peer_evidence(self):
        studies = historical_research('VOD')
        self.assertEqual(len(studies), 5)
        for section in studies.values():
            self.assertEqual(section['state'], 'NO_INSTRUMENT_MATCH')
            self.assertEqual(section['rows'], [])
