import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from flask import Flask
from application.opportunities.dashboard_activity import create_dashboard_activity_blueprint
from scripts.dashboard_clock_runner import run


class DashboardActivityTests(unittest.TestCase):
    def setUp(self):
        self.now=100.0
        app=Flask(__name__); app.register_blueprint(create_dashboard_activity_blueprint(clock=lambda:self.now))
        self.client=app.test_client()

    def send(self,client,active):
        return self.client.post('/api/v1/dashboard/activity',json={'client':client,'active':active},
                                headers={'Origin':'http://localhost'})

    def test_open_tabs_hold_independent_expiring_leases(self):
        a='a'*32; b='b'*32
        self.assertFalse(self.client.get('/api/v1/dashboard/activity').json['active'])
        self.assertTrue(self.send(a,True).json['active'])
        self.send(b,True); self.assertTrue(self.send(a,False).json['active'])
        self.now+=91
        self.assertFalse(self.client.get('/api/v1/dashboard/activity').json['active'])

    def test_cross_origin_and_remote_cannot_activate(self):
        r=self.client.post('/api/v1/dashboard/activity',json={'client':'a'*32,'active':True},
                           headers={'Origin':'https://other.example'})
        self.assertEqual(r.status_code,403)
        self.assertEqual(self.client.get('/api/v1/dashboard/activity',environ_base={'REMOTE_ADDR':'192.0.2.1'}).status_code,403)

    def test_inactive_does_not_start_clock(self):
        execute=Mock()
        result=run('calendar',activity=lambda:False,execute=execute)
        self.assertEqual(result['state'],'DORMANT_NO_RECENT_DASHBOARD_ACTIVITY')
        execute.assert_not_called()

    def test_active_starts_only_named_clock_windowlessly(self):
        execute=Mock(return_value=SimpleNamespace(returncode=0))
        result=run('radar',activity=lambda:True,execute=execute)
        self.assertEqual(result['state'],'COMPLETED')
        self.assertTrue(str(execute.call_args.args[0][1]).endswith('anticipatory_radar.py'))
        self.assertEqual(execute.call_args.args[0][2],'tick')


if __name__=='__main__': unittest.main()
