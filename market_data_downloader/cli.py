from datetime import date
from getpass import getpass

from market_data_downloader.catalog import ALL_INDICES, BROAD_INDICES, SECTORAL_INDICES
from market_data_downloader.date_ranges import parse_iso_date
from market_data_downloader.downloader import download_instrument, next_start_date
from market_data_downloader.models import InstrumentCategory, MarketInstrument
from market_data_downloader.nse_industries import (
    StockIndustryLookupError,
    classify_nse_industries,
    count_uncached_industries,
)
from market_data_downloader.paths import DATA_ROOT
from market_data_downloader.stock_catalog import (
    EQUITY_LIST_PATH,
    InstrumentMasterError,
    load_nse_stocks,
)
from market_data_downloader.storage import (
    data_file_path,
    get_last_date_from_csv,
    migrate_legacy_stock_file,
)
from market_data_downloader.upstox_client import UpstoxApiError, UpstoxClient


def _choose_instruments() -> tuple[MarketInstrument, ...]:
    print("Select data to download:")
    print("1. Broad-market indices")
    print("2. Sectoral indices")
    print("3. All supported indices")
    print("4. Select one index")
    print("5. All NSE cash-equity instruments")
    choice = input("Choice (1-5): ").strip()

    if choice == "1":
        return BROAD_INDICES
    if choice == "2":
        return SECTORAL_INDICES
    if choice == "3":
        return ALL_INDICES
    if choice == "4":
        for number, instrument in enumerate(ALL_INDICES, start=1):
            print(f"{number}. {instrument.name}")
        try:
            selected_number = int(input("Index number: ").strip())
            if not 1 <= selected_number <= len(ALL_INDICES):
                raise ValueError
            return (ALL_INDICES[selected_number - 1],)
        except (ValueError, IndexError):
            print("Invalid index selection.")
            return ()
    if choice == "5":
        try:
            catalog = load_nse_stocks()
        except InstrumentMasterError as exc:
            print(f"Could not load NSE stocks: {exc}")
            return ()
        if catalog.equity_list_refreshed:
            print("Refreshed the current NSE equity list.")
        else:
            print(
                f"WARNING: Could not refresh the NSE equity list "
                f"({catalog.equity_list_warning}). Using the saved "
                f"{EQUITY_LIST_PATH.name}, which may be outdated."
            )
            if (
                input("Continue using this saved list? (y/N): ")
                .strip()
                .lower()
                != "y"
            ):
                print("Stock download cancelled.")
                return ()
        stocks = catalog.instruments
        print(
            f"NSE currently lists {catalog.nse_eq_count:,} SERIES=EQ stocks; "
            f"{len(stocks):,} matched Upstox instrument keys. "
            "Downloading all of them can take a long time and use substantial "
            "API quota and disk space."
        )
        if catalog.unmatched_symbols:
            missing = ", ".join(catalog.unmatched_symbols[:10])
            if len(catalog.unmatched_symbols) > 10:
                missing += f", and {len(catalog.unmatched_symbols) - 10} more"
            print(
                f"Skipping {len(catalog.unmatched_symbols)} NSE listing(s) "
                f"without an Upstox instrument key: {missing}"
            )
        if (
            input("Continue with all these instruments? (y/N): ")
            .strip()
            .lower()
            != "y"
        ):
            print("Download cancelled.")
            return ()
        return stocks

    print("Invalid choice. Enter a number from 1 to 5.")
    return ()


def _read_initial_start_date() -> date:
    while True:
        value = input("Enter initial start date (YYYY-MM-DD): ").strip()
        try:
            start_date = parse_iso_date(value)
        except ValueError:
            print("Invalid date. Use YYYY-MM-DD.")
            continue
        if start_date > date.today():
            print("Start date cannot be in the future.")
            continue
        return start_date


def main() -> int:
    print("Upstox NSE Market Data Downloader")
    print("=================================")

    instruments = _choose_instruments()
    if not instruments:
        return 2

    if instruments[0].category is InstrumentCategory.STOCKS:
        cache_path = DATA_ROOT / ".stock_industry_cache.json"
        try:
            uncached_count = count_uncached_industries(instruments, cache_path)
        except StockIndustryLookupError as exc:
            print(f"Could not inspect NSE industry cache: {exc}")
            return 1

        if uncached_count:
            print(
                f"NSE sector information is missing or stale for "
                f"{uncached_count:,} stock(s). The first lookup can take a long "
                "time; results are cached for future runs."
            )
            if (
                input("Look up these sectors from NSE now? (y/N): ")
                .strip()
                .lower()
                != "y"
            ):
                print("Stock download cancelled.")
                return 2

        def report_sector_progress(
            completed: int,
            total: int,
            stock: MarketInstrument,
        ) -> None:
            if completed % 25 == 0 or completed == total:
                print(
                    f"[NSE sector lookup {completed}/{total}] "
                    f"{stock.tradingsymbol}"
                )

        try:
            instruments = classify_nse_industries(
                instruments,
                cache_path,
                on_progress=report_sector_progress,
            )
            for instrument in instruments:
                migrate_legacy_stock_file(DATA_ROOT, instrument)
        except (StockIndustryLookupError, OSError, ValueError) as exc:
            print(f"Could not classify or migrate stock data: {exc}")
            return 1

        unclassified_count = sum(
            instrument.sector_slug is None for instrument in instruments
        )
        print(
            f"NSE sector mapping complete: "
            f"{len(instruments) - unclassified_count:,} classified, "
            f"{unclassified_count:,} unclassified."
        )

    access_token = getpass("Enter your Upstox access token: ").strip()
    if not access_token:
        print("Access token is required.")
        return 2

    try:
        instruments_without_data = [
            instrument
            for instrument in instruments
            if get_last_date_from_csv(data_file_path(DATA_ROOT, instrument)) is None
        ]
    except (OSError, ValueError) as exc:
        print(f"Could not inspect existing CSV data: {exc}")
        return 1

    first_download_date = (
        _read_initial_start_date() if instruments_without_data else None
    )
    client = UpstoxClient(access_token)
    end_date = date.today()
    failed_instruments: list[str] = []
    skipped_after_error = 0

    for number, instrument in enumerate(instruments, start=1):
        try:
            start_date = next_start_date(
                DATA_ROOT,
                instrument,
                first_download_date,
            )
            if start_date > end_date:
                latest_date = get_last_date_from_csv(
                    data_file_path(DATA_ROOT, instrument)
                )
                print(f"[{number}/{len(instruments)}] {instrument.name}: current through {latest_date}.")
                continue

            print(
                f"\n[{number}/{len(instruments)}] {instrument.name}: "
                f"downloading from {start_date}..."
            )
            saved_count = download_instrument(
                client,
                DATA_ROOT,
                instrument,
                start_date,
                end_date,
            )
            if saved_count:
                print(f"{instrument.name}: saved {saved_count} candles.")
            else:
                print(f"{instrument.name}: no new candles returned.")
        except UpstoxApiError as exc:
            failed_instruments.append(instrument.name)
            print(f"{instrument.name}: download failed: {exc}")
            if (
                exc.status_code is None
                or exc.status_code in {401, 403, 429}
                or exc.status_code >= 500
            ):
                skipped_after_error = len(instruments) - number
                print("Stopping after a connection, authentication, or API-wide error.")
                break
        except (OSError, ValueError) as exc:
            failed_instruments.append(instrument.name)
            print(f"{instrument.name}: download failed: {exc}")

    if failed_instruments:
        shown_failures = ", ".join(failed_instruments[:10])
        if len(failed_instruments) > 10:
            shown_failures += f", and {len(failed_instruments) - 10} more"
        print(f"\n{len(failed_instruments)} instrument(s) failed: {shown_failures}")
    if skipped_after_error:
        print(
            f"{skipped_after_error} remaining instrument(s) were skipped. "
            "Run again to resume from each CSV's latest date."
        )
    if failed_instruments:
        return 1

    print("\nDownload run complete.")
    return 0
