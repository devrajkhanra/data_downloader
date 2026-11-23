# Upstox NSE Market Data Downloader

A modular desktop and command-line downloader for historical five-minute NSE
broad-market and sectoral indices, cash-equity instruments, and listed options
from Upstox.

The previous hard-coded May 2026 futures selection is not included because
that contract has expired.

## Requirements

- Python 3.10 or later
- An Upstox access token with historical-data API access

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

On Windows, a project-local environment avoids global Python package conflicts:

```powershell
python -m venv .venv-app
.\.venv-app\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

From PowerShell in the project folder, start the desktop app with:

```powershell
.\.venv-app\Scripts\python.exe nifty_downloader.py
```

To use the interactive CLI instead:

```powershell
.\.venv-app\Scripts\python.exe -m market_data_downloader
```

The desktop app uses PySide6 Qt Quick/QML, keeps the access token in memory,
and runs catalog loading and downloads outside the UI thread. It supports
individual index selection, stock and options downloads, progress/cancellation,
and resuming saved jobs. Existing CSVs resume from their latest dates; enter an
initial start date only when selected instruments have no data yet.

The interactive menu offers:

1. Broad-market indices
2. Sectoral indices
3. All supported indices
4. One selected index
5. All NSE cash-equity instruments
6. Listed weekly and monthly options for supported indices and F&O stocks

The access token is requested without echoing it to the terminal; do not put it
in the source code.

### NSE options

The options choice refreshes the official NSE equity list and reads the current
Upstox NSE instrument master. It includes all listed strikes and both call
(`CE`) and put (`PE`) contracts for supported indices and active NSE
`SERIES=EQ` stocks with F&O contracts. Only options for indices in the
downloader's supported catalog are included.

Only contracts still listed in the current instrument master are discovered;
expired contracts cannot be selected by entering an earlier start date. The
master does not label expiries as weekly or monthly. The downloader groups
contracts by underlying and calendar month: the last listed expiry in that
month is labeled monthly, and earlier listed expiries are labeled weekly. The
app displays the contract count and asks for confirmation before downloading;
the complete index-and-stock option list can contain tens of thousands of
contracts.

Option candles use the same five-minute interval, date-range prompt, and
per-contract resume behavior as indices and stocks. Existing CSVs resume from
their latest date; contracts without a CSV use the requested initial date.
Option files are separated by underlying, expiry type, expiry date, strike, and
call/put:

```text
data/
  options/
    indices/
      nifty50/
        weekly/
          <expiry-date>/
            <strike>-CE_data.csv
    stocks/
      reliance/
        monthly/
          <expiry-date>/
            <strike>-PE_data.csv
```

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

## Backend engine

The CLI and desktop use the same backend layers:

```text
CLI / Qt controller
        |
application.py       Composition root: constructs repositories, job stores,
        |             and the download engine with the selected provider.
download_engine.py   Bounded scheduling, cancellation, retry/resume semantics.
        |
HistoricalDataSource     MarketDataRepository     DownloadJobStore
UpstoxClient              CSV adapter              SQLite adapter
```

`DownloadApplication` is the composition root. It keeps provider, storage, and
worker setup out of the CLI and Qt controller, and its paths can be overridden
for tests or alternate deployments. The engine and repository/job-store
protocols remain the extension points for additional providers and storage
backends. `stock_service.py` centralizes sector classification and legacy-file
migration so both entry points prepare stock data identically.

The engine runs a bounded number of contracts concurrently (three by default;
configurable from one to eight in code), reports structured progress, and
stops scheduling new work after an account-wide or connection failure.
Concurrency is deliberately limited and does not bypass Upstox rate or
historical-data limits.

Job definitions and per-instrument status are stored in
`data/.download_jobs.sqlite3`; access tokens are not stored in job records.
The engine can list and resume jobs, retrying failed items. If the process stops
while an item is running, resuming recalculates its next date from the CSV so
already-saved candles are not downloaded again. The CLI currently starts a new
job each run and resumes data from each instrument's latest CSV date.

Downloaded candles are accessed through a `MarketDataRepository` interface.
`CsvMarketDataRepository` is the current implementation and can read typed
candles for a selected instrument and date range as well as save new data.
Future analysis, prediction, or forecasting features can depend on this data
interface instead of making provider requests or parsing files inside the UI.
The downloaded CSVs remain the canonical user-facing data files.

Keep new analysis and forecasting logic in application/domain modules that
depend on `MarketDataRepository`; keep API clients and file/database access in
their adapters. The UI should call application services and render their
progress/results rather than owning storage or provider details.

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
  options/
    indices/
      nifty50/
        weekly/
          <expiry-date>/
            <strike>-CE_data.csv
    stocks/
      reliance/
        monthly/
          <expiry-date>/
            <strike>-PE_data.csv
```

Index files follow
`data/<group>/<instrument-slug>/<instrument-slug>_data.csv`. Stock files
follow
`data/stocks/<sector-slug>/<stock-slug>/<stock-slug>_data.csv`. Option files
follow
`data/options/<underlying-category>/<underlying-slug>/<weekly-or-monthly>/<expiry-date>/<strike>-<CE-or-PE>_data.csv`.
Existing Nifty 50 data is now at
`data/broad_indices/nifty50/nifty50_data.csv`.

The `data/` directory is ignored for new, untracked output files. Existing CSVs
that are already tracked by Git remain tracked; `.gitignore` does not remove
them from the repository.

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
  catalog.py        # Supported index definitions and instrument keys
  cli.py            # Interactive command-line interface
  data_repository.py # CSV repository and market-data access interface
  date_ranges.py    # Date parsing and API-sized ranges
  download_engine.py # Bounded concurrent job orchestration
  downloader.py     # Per-instrument download operations
  job_models.py     # Persistent job and progress models
  job_store.py      # SQLite job state and recovery
  models.py         # Index, stock, option, and candle types
  nse_industries.py # NSE industry lookup and local cache
  option_catalog.py # Listed weekly/monthly NSE option contracts
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
