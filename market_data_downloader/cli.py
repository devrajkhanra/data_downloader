import sqlite3
from datetime import date
from getpass import getpass

from market_data_downloader.application import DownloadApplication
from market_data_downloader.catalog import ALL_INDICES, BROAD_INDICES, SECTORAL_INDICES
from market_data_downloader.date_ranges import parse_iso_date
from market_data_downloader.download_engine import DEFAULT_MAX_WORKERS
from market_data_downloader.job_models import (
    DownloadProgress,
    JobItemStatus,
    JobStatus,
)
from market_data_downloader.models import (
    DataInstrument,
    InstrumentCategory,
    MarketInstrument,
)
from market_data_downloader.nse_industries import (
    StockIndustryLookupError,
    count_uncached_industries,
)
from market_data_downloader.option_catalog import OptionCatalogError, load_option_contracts
from market_data_downloader.stock_catalog import (
    EQUITY_LIST_PATH,
    InstrumentMasterError,
    load_nse_stocks,
)
from market_data_downloader.stock_service import prepare_stock_instruments


def _choose_instruments() -> tuple[DataInstrument, ...]:
    print("Select data to download:")
    print("1. Broad-market indices")
    print("2. Sectoral indices")
    print("3. All supported indices")
    print("4. Select one index")
    print("5. All NSE cash-equity instruments")
    print("6. Listed weekly and monthly options (indices and F&O stocks)")
    choice = input("Choice (1-6): ").strip()

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

    if choice == "6":
        try:
            catalog = load_option_contracts()
        except OptionCatalogError as exc:
            print(f"Could not load option contracts: {exc}")
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
                print("Option download cancelled.")
                return ()

        contracts = catalog.contracts
        if not contracts:
            print("No currently listed option contracts matched supported underlyings.")
            return ()
        weekly_count = sum(
            contract.expiry_type == "weekly" for contract in contracts
        )
        monthly_count = len(contracts) - weekly_count
        print(
            f"Found {len(contracts):,} currently listed option contracts across "
            f"{catalog.index_underlyings} supported indices and "
            f"{catalog.stock_underlyings} active F&O stocks "
            f"({weekly_count:,} weekly and {monthly_count:,} monthly)."
        )
        print(
            "This includes every listed strike and both call/put contracts. "
            "Expired contracts are not included. Downloading this many "
            "contracts can take a long time and use substantial API quota."
        )
        if catalog.skipped_underlyings:
            print(
                f"Skipped {len(catalog.skipped_underlyings)} option underlyings "
                "not in the supported index or active NSE stock catalog."
            )
        if (
            input("Continue with all these option contracts? (y/N): ")
            .strip()
            .lower()
            != "y"
        ):
            print("Option download cancelled.")
            return ()
        return contracts

    print("Invalid choice. Enter a number from 1 to 6.")
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

    application = DownloadApplication()
    instruments = _choose_instruments()
    if not instruments:
        return 2

    if (
        isinstance(instruments[0], MarketInstrument)
        and instruments[0].category is InstrumentCategory.STOCKS
    ):
        stock_instruments = tuple(
            instrument
            for instrument in instruments
            if isinstance(instrument, MarketInstrument)
        )
        cache_path = application.data_root / ".stock_industry_cache.json"
        try:
            uncached_count = count_uncached_industries(
                stock_instruments,
                cache_path,
            )
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
            instruments = prepare_stock_instruments(
                stock_instruments,
                application.data_root,
                cache_path=cache_path,
                on_progress=report_sector_progress,
            )
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
        repository = application.create_market_data_repository()
        instruments_without_data = [
            instrument
            for instrument in instruments
            if repository.latest_date(instrument) is None
        ]
    except (OSError, ValueError) as exc:
        print(f"Could not inspect existing CSV data: {exc}")
        return 1

    first_download_date = (
        _read_initial_start_date() if instruments_without_data else None
    )
    end_date = date.today()
    try:
        job_store = application.create_job_store()
        engine = application.create_download_engine(
            access_token,
            max_workers=DEFAULT_MAX_WORKERS,
            job_store=job_store,
            repository=repository,
        )
        job_id = engine.create_job(
            tuple(instruments),
            first_download_date,
            end_date,
        )
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"Could not create download job: {exc}")
        return 1

    print(
        f"\nDownload job {job_id} queued with "
        f"{engine.max_workers} concurrent workers."
    )
    print(f"Job state is saved in {application.job_database_path}.")
    progress_interval = max(1, len(instruments) // 100)

    def report_progress(progress: DownloadProgress) -> None:
        if (
            progress.completed_items % progress_interval == 0
            or progress.completed_items == progress.total_items
            or progress.item_status is JobItemStatus.FAILED
        ):
            print(
                f"[{progress.completed_items}/{progress.total_items}] "
                f"{progress.instrument_name}: {progress.item_status.value}"
                + (
                    f", saved {progress.saved_candles} candles"
                    if progress.saved_candles
                    else ""
                )
                + (f" - {progress.error}" if progress.error else "")
            )

    try:
        job = engine.run_job(job_id, on_progress=report_progress)
    except (OSError, ValueError, RuntimeError, KeyError, sqlite3.Error) as exc:
        print(f"Download job {job_id} stopped: {exc}")
        return 1

    print(
        f"\nJob {job.status.value}: "
        f"{job.succeeded_items} downloaded, {job.no_data_items} empty, "
        f"{job.failed_items} failed, {job.pending_items} remaining."
    )
    if job.error:
        print(job.error)
    if job.status is JobStatus.COMPLETED:
        print("Download run complete.")
        return 0

    try:
        failed_items = job_store.get_items(
            job_id,
            statuses=(JobItemStatus.FAILED,),
        )
    except sqlite3.Error as exc:
        print(f"Could not read failed job items: {exc}")
        return 1
    if failed_items:
        shown_failures = ", ".join(
            item.instrument.name for item in failed_items[:10]
        )
        if len(failed_items) > 10:
            shown_failures += f", and {len(failed_items) - 10} more"
        print(f"Failed instruments: {shown_failures}")
    print("Existing CSV data is preserved; rerun the download to resume.")
    return 1
