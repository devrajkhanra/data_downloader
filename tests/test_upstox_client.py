import unittest
from datetime import date

from market_data_downloader.upstox_client import UpstoxApiError, UpstoxClient


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.urls = []
        self.headers = []
        self.timeouts = []

    def get(self, url, headers, timeout):
        self.urls.append(url)
        self.headers.append(headers)
        self.timeouts.append(timeout)
        return next(self.responses)


class UpstoxClientTests(unittest.TestCase):
    def test_requests_are_encoded_and_split_into_calendar_months(self):
        candle = ["2026-10-27T09:15:00+05:30", 1, 2, 0, 1, 0, 0]
        payload = {"status": "success", "data": {"candles": [candle]}}
        session = FakeSession([FakeResponse(payload), FakeResponse(payload)])
        client = UpstoxClient("test-token", session=session)

        result = client.get_historical_candles(
            "NSE_INDEX|Nifty 50",
            date(2026, 10, 27),
            date(2026, 11, 2),
        )

        self.assertEqual(len(session.urls), 2)
        self.assertIn("NSE_INDEX%7CNifty%2050/minutes/5/2026-10-31/2026-10-27", session.urls[0])
        self.assertIn("NSE_INDEX%7CNifty%2050/minutes/5/2026-11-02/2026-11-01", session.urls[1])
        self.assertEqual(len(result), 1)
        self.assertEqual(session.headers[0]["Authorization"], "Bearer test-token")
        self.assertEqual(session.timeouts, [30, 30])

    def test_api_errors_are_reported(self):
        session = FakeSession([FakeResponse({"status": "error", "message": "Invalid key"})])
        client = UpstoxClient("test-token", session=session)

        with self.assertRaisesRegex(UpstoxApiError, "Invalid key"):
            client.get_historical_candles(
                "NSE_INDEX|invalid",
                date(2026, 10, 27),
                date(2026, 10, 27),
            )

    def test_rejects_minute_intervals_outside_v3_documented_range(self):
        client = UpstoxClient("test-token", session=FakeSession([]))
        with self.assertRaises(ValueError):
            client.get_historical_candles(
                "NSE_INDEX|Nifty 50",
                date(2026, 10, 27),
                date(2026, 10, 27),
                interval_minutes=30,
            )


if __name__ == "__main__":
    unittest.main()
