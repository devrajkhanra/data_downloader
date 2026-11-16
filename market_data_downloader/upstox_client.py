from datetime import date
from urllib.parse import quote
from typing import cast

import requests

from market_data_downloader.date_ranges import month_ranges
from market_data_downloader.models import Candle
from market_data_downloader.sessions import create_retrying_session


API_BASE_URL = "https://api.upstox.com/v3"
REQUEST_TIMEOUT_SECONDS = 30


class UpstoxApiError(RuntimeError):
    """Raised when an Upstox historical-data request cannot be completed."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class UpstoxClient:
    def __init__(
        self,
        access_token: str,
        session: requests.Session | None = None,
        timeout: int = REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        if not access_token.strip():
            raise ValueError("Access token is required.")
        self._session = session if session is not None else create_retrying_session()
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
                response = getattr(exc, "response", None)
                status_code = getattr(response, "status_code", None)
                raise UpstoxApiError(
                    f"Request failed for {instrument_key} "
                    f"({chunk_start} through {chunk_end}): {exc}",
                    status_code=status_code,
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
                    f"Upstox API error for {instrument_key}: {message}",
                    status_code=getattr(response, "status_code", None),
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
