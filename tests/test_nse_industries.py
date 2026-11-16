import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import requests

from market_data_downloader.models import InstrumentCategory, MarketInstrument
from market_data_downloader.nse_industries import (
    StockIndustryLookupError,
    classify_nse_industries,
    count_uncached_industries,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, api_responses=None):
        self.api_responses = list(api_responses or [])
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if "GetQuoteApi" in url:
            return self.api_responses.pop(0)
        return FakeResponse()


def stock():
    return MarketInstrument(
        name="Example Corp",
        instrument_key="NSE_EQ|INE000A01001",
        category=InstrumentCategory.STOCKS,
        slug="example",
        tradingsymbol="EXAMPLE",
    )


class NseIndustryTests(unittest.TestCase):
    def test_fetches_sector_and_caches_it(self):
        session = FakeSession(
            [
                FakeResponse(
                    payload={
                        "equityResponse": [
                            {
                                "secInfo": {
                                    "sector": "Financial Services",
                                }
                            }
                        ]
                    }
                )
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "industry-cache.json"
            with patch("market_data_downloader.nse_industries.time.sleep"):
                classified = classify_nse_industries(
                    (stock(),),
                    cache_path,
                    session=session,
                    today=date(2026, 11, 14),
                )

            self.assertEqual(classified[0].sector_slug, "financial-services")
            self.assertEqual(len(session.calls), 1)
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(
                cache["NSE_EQ|INE000A01001"],
                {
                    "checked_on": "2026-11-14",
                    "sector": "Financial Services",
                },
            )
            self.assertEqual(count_uncached_industries(
                (stock(),),
                cache_path,
                today=date(2026, 11, 14),
            ), 0)

    def test_reuses_fresh_cache_without_network_requests(self):
        session = FakeSession()
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "industry-cache.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "NSE_EQ|INE000A01001": {
                            "checked_on": "2026-11-14",
                            "sector": "Information Technology",
                        }
                    }
                ),
                encoding="utf-8",
            )

            classified = classify_nse_industries(
                (stock(),),
                cache_path,
                session=session,
                today=date(2026, 11, 14),
            )

            self.assertEqual(classified[0].sector_slug, "information-technology")
            self.assertEqual(session.calls, [])

    def test_stops_and_reports_when_nse_blocks_lookup(self):
        session = FakeSession(
            [
                FakeResponse(status_code=403),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "industry-cache.json"

            with self.assertRaises(StockIndustryLookupError) as context:
                classify_nse_industries(
                    (stock(),),
                    cache_path,
                    session=session,
                    today=date(2026, 11, 14),
                )

            self.assertEqual(context.exception.status_code, 403)
            self.assertEqual(json.loads(cache_path.read_text(encoding="utf-8")), {})

    def test_rejects_unexpected_nse_response_shape(self):
        session = FakeSession([FakeResponse(payload={"message": "unexpected"})])
        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "industry-cache.json"

            with self.assertRaisesRegex(
                StockIndustryLookupError,
                "unexpected industry response",
            ):
                classify_nse_industries(
                    (stock(),),
                    cache_path,
                    session=session,
                    today=date(2026, 11, 14),
                )


if __name__ == "__main__":
    unittest.main()
