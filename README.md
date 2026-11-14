# Upstox NSE Index Data Downloader

A modular command-line downloader for historical five-minute NSE broad-market
and sectoral index candles from Upstox.

This version downloads NSE index data. The previous hard-coded May 2026 futures
selection is not included because that contract has expired.

## Requirements

- Python 3.10 or later
- An Upstox access token with historical-data API access

Install the dependency:

```powershell
python -m pip install -r requirements.txt
```

## Run

From a terminal, run either command from the project folder:

```powershell
python nifty_downloader.py
```

or:

```powershell
python -m market_data_downloader
```

Choose broad indices, sectoral indices, all supported indices, or one index.
The access token is requested without echoing it to the terminal; do not put it
in the source code.

### Broad-market indices

- Nifty 50
- Nifty Next 50
- Nifty 100
- Nifty 200
- Nifty 500
- Nifty Midcap 50
- Nifty Midcap 100
- Nifty Midcap 150
- Nifty Smallcap 50
- Nifty Smallcap 100
- Nifty Smallcap 250
- Nifty LargeMidcap 250
- Nifty MidSmallcap 400
- Nifty Microcap 250
- Nifty Total Market
- Nifty 500 Multicap
- Nifty Mid Select

### Sectoral indices

- Nifty Auto
- Nifty Bank
- Nifty Financial Services
- Nifty Financial Services 25/50
- Nifty Financial Services Ex-Bank
- Nifty FMCG
- Nifty IT
- Nifty Media
- Nifty Metal
- Nifty Pharma
- Nifty PSU Bank
- Nifty Private Bank
- Nifty Realty
- Nifty Healthcare
- Nifty Consumer Durables
- Nifty Oil & Gas
- Nifty Chemicals
- Nifty Cement
- Nifty Energy
- Nifty Infrastructure
- Nifty Services Sector

The instrument keys for these catalogs are verified against Upstox's
[NSE instrument master](https://assets.upstox.com/market-quote/instruments/exchange/NSE.csv.gz).

## Dates and resuming

For each selected index, the downloader reads that index's CSV and starts from
the day after its latest date. If an index has no CSV yet, it asks for an
initial `YYYY-MM-DD` start date. When a group contains both existing and new
indexes, the new indexes use the entered date while existing indexes resume
independently.

## Output layout

CSV files are saved under the project folder, regardless of the terminal's
current working directory. Each index has its own folder and CSV:

```text
data/
  broad_indices/
    nifty50/
      nifty50_data.csv
    nifty-next-50/
      nifty-next-50_data.csv
    ...
  sectoral_indices/
    nifty-auto/
      nifty-auto_data.csv
    nifty-bank/
      nifty-bank_data.csv
    ...
```

The filename pattern is `data/<group>/<index-slug>/<index-slug>_data.csv`.
Existing Nifty 50 data is now at
`data/broad_indices/nifty50/nifty50_data.csv`.

## API behavior

- Uses Upstox [Historical Candle Data V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/).
- Five-minute requests are split into calendar-month ranges to stay within the
  API's historical retrieval limits for minute intervals.
- Transient HTTP errors and rate limits are retried.
- Candles are merged by timestamp and saved in timestamp order. An empty API
  response does not replace existing CSV data.
- Historical minute data availability starts in January 2022, subject to
  Upstox instrument and account availability.

## Project structure

```text
market_data_downloader/
  catalog.py       # Supported index definitions and instrument keys
  cli.py           # Interactive command-line interface
  date_ranges.py   # Date parsing and API-sized ranges
  downloader.py    # Per-index resume and download workflow
  models.py        # Index and candle types
  paths.py         # Project and data roots
  storage.py       # CSV read, merge, and write operations
  upstox_client.py # Upstox V3 HTTP client
tests/             # Offline unit tests
```

To add an index, add an `IndexInstrument` entry to the appropriate catalog in
`market_data_downloader/catalog.py` with its Upstox key and a unique slug.

Run the offline tests with:

```powershell
python -m unittest discover -v
```
