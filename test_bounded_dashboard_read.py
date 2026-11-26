"""Exercise overlap, timeout and cached retry for retained Dashboard reads."""
from threading import Event
import unittest

from flask import Flask, jsonify, request

from application.bounded_dashboard_read import retained_read


class BoundedDashboardReadTests(unittest.TestCase):
    def test_timed_out_read_can_be_retried_without_duplicate_work(self):
        app = Flask(__name__)
        started, release, finished = Event(), Event(), Event()
        calls = []

        @app.get('/read')
        @retained_read(workers=1, wait_seconds=0.01)
        def retained():
            calls.append(request.args['id'])
            started.set()
            try:
                release.wait(2)
                return jsonify(query=request.args['id'])
            finally:
                finished.set()

        with app.test_client() as client:
            try:
                result = client.get('/read?id=one')
                self.assertEqual((result.status_code, result.json['state']), (503, 'READ_TIMED_OUT'))
                self.assertTrue(started.wait(1))
                self.assertEqual(client.get('/read?id=one').status_code, 503)
                self.assertEqual(client.get('/read?id=two').status_code, 503)
                self.assertEqual(calls, ['one'])
            finally:
                release.set()
            self.assertTrue(finished.wait(1))
            self.assertEqual(client.get('/read?id=one').json, {'query': 'one'})
            self.assertEqual(client.get('/read?id=one').json, {'query': 'one'})
            self.assertEqual(calls, ['one'])

    def test_unsuccessful_result_is_not_cached(self):
        app = Flask(__name__)
        calls = []

        @app.get('/read')
        @retained_read()
        def retained():
            calls.append(1)
            return jsonify(state='UNAVAILABLE'), 404

        with app.test_client() as client:
            for attempt in range(2):
                self.assertEqual(client.get('/read').status_code, 404)
            self.assertEqual(len(calls), 2)
