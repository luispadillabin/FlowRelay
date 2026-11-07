import concurrent.futures
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from relay import Queue, ValidationError, ConflictError
from server import handler_for


def event(id='evt-1', fail=0):
    return {'event_id': id, 'event_type': 'ticket.created', 'payload': {'fail_until': fail}}


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 1000
        self.q = Queue(Path(self.tmp.name) / 'test.db', lambda: self.now)

    def tearDown(self):
        self.tmp.cleanup()

    def test_duplicate_and_conflict(self):
        self.assertTrue(self.q.submit(event())[1])
        self.assertFalse(self.q.submit(event())[1])
        with self.assertRaises(ConflictError):
            self.q.submit(event(fail=1))
        self.assertEqual(self.q.list()['total'], 1)

    def test_success_not_processed_twice(self):
        self.q.submit(event())
        self.assertEqual(self.q.process()['status'], 'succeeded')
        self.assertIsNone(self.q.process())
        self.assertEqual(len(self.q.detail('evt-1')['history']), 1)

    def test_retry_boundary(self):
        self.q.submit(event(fail=1))
        self.assertEqual(self.q.process()['next_attempt'], 1002)
        self.now = 1001.99
        self.assertIsNone(self.q.process())
        self.now = 1002
        self.assertEqual(self.q.process()['status'], 'succeeded')

    def test_dead_letter_and_history(self):
        self.q.submit(event(fail=10))
        self.q.process()
        self.now = 1002
        self.assertEqual(self.q.process()['next_attempt'], 1006)
        self.now = 1006
        self.assertEqual(self.q.process()['status'], 'dead_letter')
        self.assertIsNone(self.q.process())
        self.assertEqual([a['attempt'] for a in self.q.detail('evt-1')['history']], [1, 2, 3])

    def test_restart_persistence(self):
        self.q.submit(event())
        other = Queue(self.q.path)
        self.assertEqual(other.list()['total'], 1)

    def test_validation(self):
        for bad in [None, [], {}, event('../bad'), {**event(), 'extra': 1}, event(fail=True), event(fail=-1), event(fail=11), {**event(), 'payload': []}, {**event(), 'payload': {'unknown': 1}}]:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                self.q.submit(bad)
        self.assertEqual(self.q.list()['total'], 0)

    def test_parallel_submission(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.q.submit(event())[1], range(8)))
        self.assertEqual(sum(results), 1)

    def test_parallel_processing(self):
        self.q.submit(event())
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.q.process(), range(8)))
        self.assertEqual(sum(r is not None for r in results), 1)


class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(Queue(Path(self.tmp.name) / 'api.db')))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, method, path, data=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        body = json.dumps(data) if data is not None else None
        h = {'Content-Type': 'application/json', **(headers or {})}
        conn.request(method, path, body, h)
        response = conn.getresponse()
        result = (response.status, response.read())
        conn.close()
        return result

    def test_full_api_flow(self):
        self.assertEqual(self.request('POST', '/api/events', event())[0], 201)
        self.assertEqual(self.request('POST', '/api/events', event())[0], 200)
        self.assertEqual(self.request('POST', '/api/events', event(fail=1))[0], 409)
        status, raw = self.request('POST', '/api/process', {})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['processed']['status'], 'succeeded')
        self.assertEqual(self.request('GET', '/api/events/evt-1')[0], 200)
        self.assertEqual(self.request('GET', '/api/events/missing')[0], 404)

    def test_origin_content_and_size(self):
        self.assertEqual(self.request('POST', '/api/events', event(), {'Origin': 'https://elsewhere.example'})[0], 403)
        self.assertEqual(self.request('POST', '/api/events', event(), {'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.request('POST', '/api/events', {'large': 'a'*17000})[0], 413)

    def test_malformed_duplicate_keys(self):
        for body in ['{', '{"x":1,"x":2}', 'NaN']:
            conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
            conn.request('POST', '/api/events', body, {'Content-Type': 'application/json'})
            response = conn.getresponse()
            self.assertEqual(response.status, 400)
            response.read()
            conn.close()

    def test_dashboard_and_routes(self):
        self.assertIn(b'FlowRelay', self.request('GET', '/')[1])
        for path in ['/app.js', '/styles.css', '/api/health', '/api/events']:
            self.assertEqual(self.request('GET', path)[0], 200)
        self.assertEqual(self.request('GET', '/../server.py')[0], 404)
        self.assertEqual(self.request('POST', '/api/process', {'bad': 1})[0], 400)


if __name__ == '__main__':
    unittest.main()
