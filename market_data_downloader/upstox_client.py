from datetime import date
from urllib.parse import quote
from typing import cast

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from market_data_downloader.date_ranges import month_ranges
from market_data_downloader.models import Candle


API_BASE_URL = "https://api.upstox.com/v3"
REQUEST_TIMEOUT_SECONDS = 30


class UpstoxApiError(RuntimeError):
    """Raised when an Upstox historical-data request cannot be completed."""


def _create_session() -> requests.Session:
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    return session


class UpstoxClient:
    def __init__(
        self,
        access_token: str,
        session: requests.Session | None = None,
        timeout: int = REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        if not access_token.strip():
            raise ValueError("Access token is required.")
        self._session = session or _create_session()
        self._timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    def get_historical_candles(
        self,
        instrument_key: str,
        start_date: date,
        end_date: date,
        interval_minutes: int = 5,
    ) -> list[Candle]:
        if not 1 <= interval_minutes <= 15:
            raise ValueError("Historical minute intervals must be from 1 to 15.")
        if start_date > end_date:
            return []

        encoded_key = quote(instrument_key, safe="")
        candles_by_timestamp: dict[str, Candle] = {}
        for chunk_start, chunk_end in month_ranges(start_date, end_date):
            url = (
                f"{API_BASE_URL}/historical-candle/{encoded_key}/minutes/"
                f"{interval_minutes}/{chunk_end.isoformat()}/{chunk_start.isoformat()}"
            )
            try:
                response = self._session.get(
                    url,
                    headers=self._headers,
                    timeout=self._timeout,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                raise UpstoxApiError(
                    f"Request failed for {instrument_key} "
                    f"({chunk_start} through {chunk_end}): {exc}"
                ) from exc

            try:
                payload = response.json()
            except ValueError as exc:
                raise UpstoxApiError("Upstox returned invalid JSON.") from exc

            if not isinstance(payload, dict) or payload.get("status") != "success":
                message = (
                    payload.get("message", "Unknown API error")
                    if isinstance(payload, dict)
                    else "Unexpected API response"
                )
                raise UpstoxApiError(
                    f"Upstox API error for {instrument_key}: {message}"
                )

            data = payload.get("data")
            candles = data.get("candles") if isinstance(data, dict) else None
            if not isinstance(candles, list):
                raise UpstoxApiError(
                    f"Upstox response did not contain candles for {instrument_key}."
                )

            for candle in candles:
                if (
                    not isinstance(candle, list)
                    or len(candle) != 7
                    or not isinstance(candle[0], str)
                    or not all(
                        value is None or isinstance(value, (str, int, float))
                        for value in candle[1:]
                    )
                ):
                    raise UpstoxApiError(
                        f"Upstox returned a malformed candle for {instrument_key}."
                    )
                candles_by_timestamp[candle[0]] = cast(Candle, candle)

        return [
            candles_by_timestamp[timestamp]
            for timestamp in sorted(candles_by_timestamp)
        ]
