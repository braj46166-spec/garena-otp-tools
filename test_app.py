import unittest
from unittest.mock import patch

from app import app, users_db


class ApiUpdateTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        users_db.clear()
        users_db['demo'] = {'password': '1234', 'credits': 1}

    def test_send_code_get_uses_query_string_and_returns_success_json(self):
        class FakeResponse:
            status_code = 200

            def __init__(self):
                self.headers = {'content-type': 'application/json'}

            def json(self):
                return {'status': 'success'}

        with patch('app.requests.get', return_value=FakeResponse()) as mocked_get:
            response = self.client.get('/send_code', query_string={'email': 'braj46166@gmail.com'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'status': 'success'})
        mocked_get.assert_called_once()
        self.assertEqual(mocked_get.call_args.args[0], 'https://exeotp.onrender.com/send_code')
        self.assertEqual(mocked_get.call_args.kwargs['params'], {'email': 'braj46166@gmail.com'})
        self.assertEqual(mocked_get.call_args.kwargs['timeout'], 15)

    def test_send_code_route_mapping_matches_the_test_url(self):
        rule = next((r for r in app.url_map.iter_rules() if r.rule == '/send_code'), None)

        self.assertIsNotNone(rule)
        self.assertIn('GET', rule.methods)
        self.assertEqual(rule.rule, '/send_code')


if __name__ == '__main__':
    unittest.main()
