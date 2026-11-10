import unittest
import json
import tempfile
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import application.strategy_radar.benchmark_refresh as refresh_module
from application.strategy_radar.benchmark_refresh import resolve_benchmark_chart

NOW = datetime(2026,11,9,18,tzinfo=timezone.utc)

def daily(session='2026-11-06', state='SINGLE_SOURCE', stamp='2026-11-09T10:00:00+00:00'):
    fields = {key:{'value':100, 'state':state, 'acquired_at':stamp} for key in ('open','high','low','close','volume')}
    return {'latest_session':session, 'history':{'rows':[{'session':session,'fields':fields}]}}

class BenchmarkRefreshTests(unittest.TestCase):
    def setUp(self):
        with refresh_module._lock:
            refresh_module._memo.clear(); refresh_module._pending.clear()
        executor=type('Immediate', (), {'submit':lambda self, work:work()})()
        patcher=patch.object(refresh_module,'_executor',executor); patcher.start(); self.addCleanup(patcher.stop)
        self.service=Mock(); self.service.clock.return_value=NOW; self.service.folder='unused'; self.service.root='unused'
        self.service.prewarm.return_value={'watches':{'ETF_STX40':daily()}}

    @patch('application.strategy_radar.benchmark_refresh._chart',return_value=None)
    def test_stale_cache_rereads_local_only(self, unused):
        self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40')[1],'LOCAL_REFRESH_PENDING')
        chart,status=resolve_benchmark_chart(self.service,'ETF_STX40')
        self.assertEqual(status,'LOCAL_REFRESH'); self.assertEqual(chart['bars'][0]['close'],100)
        self.service.prewarm.assert_called_once_with(['ETF_STX40'],root=refresh_module.Path('unused').resolve(),now=NOW)

    @patch('application.strategy_radar.benchmark_refresh._chart',return_value=None)
    def test_close_only_is_not_converted_to_ohlc(self, unused):
        result=daily(); row=result['history']['rows'][0]
        row['fields']={'close':row['fields']['close']}
        self.service.prewarm.return_value={'watches':{'ETF_STX40':result}}
        self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40')[1],'LOCAL_REFRESH_PENDING')
        chart,status=resolve_benchmark_chart(self.service,'ETF_STX40')
        self.assertEqual(status,'LOCAL_REFRESH')
        self.assertEqual(set(chart['bars'][0]), {'timestamp','close'})

    @patch('application.strategy_radar.benchmark_refresh._chart',return_value={'bars':[{'close':100}]})
    def test_current_cache_does_not_reload(self, unused):
        chart,status=resolve_benchmark_chart(self.service,'ETF_STX40')
        self.assertEqual(status,'CURRENT_CACHE'); self.service.prewarm.assert_not_called()

    @patch('application.strategy_radar.benchmark_refresh._chart',return_value=None)
    def test_stale_conflicting_future_and_unknown_calendar_fail_closed(self, unused):
        for row in (daily(session='2026-11-05'),daily(state='CONFLICT'),daily(stamp='2026-11-10T10:00:00+00:00')):
            with refresh_module._lock: refresh_module._memo.clear()
            self.service.prewarm.return_value={'watches':{'ETF_STX40':row}}
            self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40')[1],'LOCAL_REFRESH_PENDING')
            self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40')[1],'LOCAL_REFRESH_UNAVAILABLE')
        self.service.prewarm.reset_mock()
        self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40',now=datetime(2027,2,1,tzinfo=timezone.utc))[1],'CALENDAR_UNAVAILABLE')
        self.service.prewarm.assert_not_called()

    def test_invalid_key_and_naive_time(self):
        self.assertEqual(resolve_benchmark_chart(self.service,'../../secret')[1],'INVALID_BENCHMARK')
        with self.assertRaises(ValueError): resolve_benchmark_chart(self.service,'ETF_STX40',now=datetime(2026,11,9))

    def test_stale_exact_target_uses_retained_dates_without_inventing_gaps(self):
        with tempfile.TemporaryDirectory() as folder:
            cache=refresh_module.Path(folder)/'daily-cache'; cache.mkdir()
            rows=[]
            for day in ['2026-10-29','2026-11-02','2026-11-03','2026-11-05','2026-11-06']:
                rows.append({'session':day,'fields':{'close':{'value':100, 'source':'IRESS','state':'SINGLE_SOURCE','acquired_at':'2026-11-09T10:00:00+00:00'}}})
            (cache/'ETF_STX40.json').write_text(json.dumps({'daily':{'history':{'rows':rows}}}))
            self.service.folder=folder
            chart,status=resolve_benchmark_chart(self.service,'ETF_STX40',target_session='2026-11-05')
            self.assertEqual(status,'CACHE_STALE')
            self.assertEqual(chart['bars'][-1]['timestamp'][:10],'2026-11-05')
            self.assertNotIn('2026-11-06',[bar['timestamp'][:10] for bar in chart['bars']])
            self.assertTrue(chart['data_quality']['stale'])
            self.assertTrue(chart['data_quality']['session_gaps_or_unknown_adjacency'])
            self.assertEqual(chart['data_quality']['fields'][-1]['source'],'IRESS')
            self.service.prewarm.assert_not_called()

    def test_retained_evidence_rejects_invalid_alternatives_and_noncanonical_dates(self):
        stamp = '2026-11-09T10:00:00+00:00'
        valid = {'source':'YAHOO', 'value':99, 'acquired_at':stamp}
        invalid = [dict(valid, source=' '), dict(valid, source=42), dict(valid, value=0),
                   dict(valid, value=-1), dict(valid, value='NaN'), dict(valid, value='bad')]
        close = {'source':'IRESS', 'value':100, 'state':'CONFLICT_NO_CONSENSUS',
                 'acquired_at':stamp, 'source_sha256':'abc', 'upstream_independence':'independent',
                 'alternatives':[valid] + invalid}
        rows = [{'session':'20261105', 'fields':{'close':close}},
                {'session':'2026-11-06', 'fields':{'close':close}}]
        chart = refresh_module._retained_target('ETF_STX40', {'history':{'rows':rows}}, NOW, '2026-11-06')
        self.assertEqual(len(chart['bars']), 1)
        field = chart['data_quality']['fields'][0]
        self.assertEqual(field['alternatives'], [valid])
        self.assertEqual(field['alternatives_omitted_unqualified'], len(invalid))
        self.assertEqual((field['value'], field['source_sha256'], field['upstream_independence']), (100, 'abc', 'independent'))
        close['source'] = ' '
        self.assertIsNone(refresh_module._retained_target('ETF_STX40', {'history':{'rows':rows}}, NOW, '2026-11-06'))
        self.assertIsNone(refresh_module._retained_target('ETF_STX40', {'history':{'rows':rows}}, NOW, '20261106'))

    def test_conflict_priority_is_provisional_and_future_alternatives_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            cache=refresh_module.Path(folder)/'daily-cache'; cache.mkdir()
            row={'session':'2026-11-06','fields':{'close':{'value':100,'source':'IRESS','state':'CONFLICT_NO_CONSENSUS','acquired_at':'2026-11-09T10:00:00+00:00','alternatives':[{'source':'YAHOO','value':99,'acquired_at':'2026-11-09T09:00:00+00:00'},{'source':'FUTURE','value':101,'acquired_at':'2026-11-10T09:00:00+00:00'}]}}}
            (cache/'ETF_STX40.json').write_text(json.dumps({'daily':{'history':{'rows':[row]}}}))
            self.service.folder=folder
            chart,status=resolve_benchmark_chart(self.service,'ETF_STX40',target_session='2026-11-06')
            self.assertEqual(status,'CACHE_PROVISIONAL')
            q=chart['data_quality']; self.assertTrue(q['provisional'])
            self.assertEqual([a['source'] for a in q['fields'][0]['alternatives']],['YAHOO'])
            self.assertEqual(q['fields'][0]['alternatives_omitted_unqualified'],1)
            self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40',target_session='2026-11-10')[1], 'INVALID_TARGET_SESSION')

    @patch('application.strategy_radar.benchmark_refresh._chart',return_value=None)
    def test_missing_exact_target_never_substitutes_latest(self, unused):
        self.service.prewarm.return_value={'watches':{'ETF_STX40':daily()}}
        self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40',target_session='2026-11-05')[1], 'LOCAL_REFRESH_PENDING')
        self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40',target_session='2026-11-05')[1], 'LOCAL_REFRESH_UNAVAILABLE')

    def test_stale_target_can_recover_from_local_archive_without_writing_cache(self):
        row={'session':'2026-11-05','fields':{'close':{'value':91,'source':'IRESS','state':'SINGLE_SOURCE','acquired_at':'2026-11-09T10:00:00+00:00'}}}
        self.service.prewarm.return_value={'watches':{'ETF_STX40':{'history':{'rows':[row]}}}}
        self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40',target_session='2026-11-05')[1], 'LOCAL_REFRESH_PENDING')
        chart,status=resolve_benchmark_chart(self.service,'ETF_STX40',target_session='2026-11-05')
        self.assertEqual(status,'LOCAL_REFRESH_STALE')
        self.assertEqual(chart['bars'][0]['close'],91)
        self.assertEqual(chart['data_quality']['fields'][0]['received_at'], '2026-11-09T10:00:00+00:00')
        self.service.prewarm.assert_called_once()

    @patch('application.strategy_radar.benchmark_refresh._chart',return_value=None)
    def test_pending_deduplicates_without_blocking_and_rolls_session(self, unused):
        queued=[]
        class Deferred:
            def submit(self, task): queued.append(task)
        with patch.object(refresh_module,'_executor',Deferred()), patch.object(refresh_module,'monotonic',return_value=10):
            self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40')[1],'LOCAL_REFRESH_PENDING')
            self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40')[1],'LOCAL_REFRESH_PENDING')
            self.assertEqual(len(queued),1)
            self.service.prewarm.assert_not_called()
            queued.pop()()
            self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40')[1],'LOCAL_REFRESH')
            later=datetime(2026,11,10,18,tzinfo=timezone.utc)
            self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40',now=later)[1],'LOCAL_REFRESH_PENDING')
            self.assertEqual(len(queued),1)

    @patch('application.strategy_radar.benchmark_refresh._chart',return_value=None)
    def test_failure_is_cached_and_expires(self, unused):
        self.service.prewarm.side_effect=OSError('local archive unavailable')
        with patch.object(refresh_module,'monotonic',return_value=10):
            self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40')[1],'LOCAL_REFRESH_PENDING')
            self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40')[1],'LOCAL_REFRESH_UNAVAILABLE')
            self.service.prewarm.assert_called_once()
        with patch.object(refresh_module,'monotonic',return_value=71):
            self.assertEqual(resolve_benchmark_chart(self.service,'ETF_STX40')[1],'LOCAL_REFRESH_PENDING')
            self.assertEqual(self.service.prewarm.call_count,2)

if __name__ == '__main__': unittest.main()
