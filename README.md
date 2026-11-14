# Nifty Data Downloader

This Python script downloads historical 5-minute candle data for Nifty 50 spot or futures from Upstox API.

## Prerequisites

1. Upstox account with API access
2. Access token from Upstox Developer Dashboard

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the script from a terminal:
```bash
python nifty_downloader.py
```

1. Select data type: 'spot' for Nifty 50 index or 'future' for Nifty futures (currently set to May 2026 expiry)
2. Enter your access token
3. Enter start date in YYYY-MM-DD format

Spot data is saved to `nifty50_data.csv`; futures data is saved to `future_data.csv`.
Files are saved next to `nifty_downloader.py`, regardless of the terminal's current
working directory.

## Notes

- Data is available from January 2022 onwards
- For date ranges longer than 1 month, the script automatically splits requests
- Requires active internet connection
- Check Upstox API rate limits
- Futures expiry is hardcoded; modify the script for different expiries

## Troubleshooting

- Ensure access token is valid and not expired
- Verify date format is YYYY-MM-DD
- Check network connectivity
- For API errors, refer to Upstox documentation