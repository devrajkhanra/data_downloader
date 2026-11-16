# Upstox NSE Market Data Downloader

A modular command-line downloader for historical five-minute NSE broad-market
and sectoral index candles, plus NSE cash-equity instruments, from Upstox.

The previous hard-coded May 2026 futures selection is not included because
that contract has expired.

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

Choose broad indices, sectoral indices, all supported indices, one index, or all
NSE cash-equity instruments. The access token is requested without echoing it
to the terminal; do not put it in the source code.

### NSE stocks

The stock option refreshes the official NSE
[Securities Available for Trading CSV](https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv)
and includes only rows whose `SERIES` is `EQ`. The refreshed list is saved as
`EQUITY_L.csv`. NSE ISINs are matched to Upstox `NSE_EQ` instrument keys, so
delisted, suspended, or other non-`EQ` series are excluded. Current NSE symbols
and company names are used; active listings without an Upstox key are reported
and skipped. If the NSE refresh fails, an existing local list can be used after
the user confirms; the downloader warns that this snapshot may be outdated.

The menu displays the current instrument count and asks for confirmation before
starting. NSE industry lookups assign each instrument to its official sector;
unclassified entries go under `unclassified`. Lookup results are cached for 30
days in `data/.stock_industry_cache.json`, and the cache is not committed.
The first lookup may take a long time; NSE must be reachable and may rate-limit
requests. If the lookup fails, the downloader stops before downloading stocks
rather than guessing sectors.

Downloading thousands of instruments can also take a long time and use
substantial Upstox API quota and disk space. Progress is reported, and rerunning
the downloader resumes each CSV independently. Existing flat stock CSVs are
moved into their sector folders and merged if a destination already exists.

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

For each selected instrument, the downloader reads its CSV and starts from the
day after its latest date. If any selected instrument has no CSV yet, it asks
for an initial `YYYY-MM-DD` start date. Existing instruments resume
independently from their own CSV dates.

## Output layout

CSV files are saved under the project folder, regardless of the terminal's
current working directory. Each instrument has its own folder and CSV:

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
  stocks/
    oil-gas-consumable-fuels/
      reliance/
        reliance_data.csv
    information-technology/
      tcs/
        tcs_data.csv
    unclassified/
    ...
```

Index files follow
`data/<group>/<instrument-slug>/<instrument-slug>_data.csv`. Stock files
follow
`data/stocks/<sector-slug>/<stock-slug>/<stock-slug>_data.csv`.
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
  downloader.py    # Per-instrument resume and download workflow
  models.py        # Instrument and candle types
  nse_industries.py # NSE industry lookup and local cache
  paths.py          # Project and data roots
  sessions.py       # Shared HTTP retries
  stock_catalog.py  # Dynamic NSE cash-equity catalog
  storage.py        # CSV read, merge, and write operations
  upstox_client.py  # Upstox V3 HTTP client
tests/             # Offline unit tests
```

To add a supported index, add an instrument entry to the appropriate catalog
in `market_data_downloader/catalog.py` with its Upstox key and a unique slug.

Run the offline tests with:

```powershell
python -m unittest discover -v
```
