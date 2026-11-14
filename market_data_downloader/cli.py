from datetime import date
from getpass import getpass

from market_data_downloader.catalog import ALL_INDICES, BROAD_INDICES, SECTORAL_INDICES
from market_data_downloader.date_ranges import parse_iso_date
from market_data_downloader.downloader import download_index, next_start_date
from market_data_downloader.models import IndexInstrument
from market_data_downloader.paths import DATA_ROOT
from market_data_downloader.storage import data_file_path, get_last_date_from_csv
from market_data_downloader.upstox_client import UpstoxApiError, UpstoxClient


def _choose_indices() -> tuple[IndexInstrument, ...]:
    print("Select index group:")
    print("1. Broad market indices")
    print("2. Sectoral indices")
    print("3. All supported indices")
    print("4. Select one index")
    choice = input("Choice (1-4): ").strip()

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

    print("Invalid choice. Enter a number from 1 to 4.")
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
    print("Upstox NSE Index Data Downloader")
    print("================================")

    instruments = _choose_indices()
    if not instruments:
        return 2

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
    failed_indices: list[str] = []

    for instrument in instruments:
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
                print(f"{instrument.name}: already current through {latest_date}.")
                continue

            print(f"\n{instrument.name}: downloading from {start_date}...")
            saved_count = download_index(
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
        except (UpstoxApiError, OSError, ValueError) as exc:
            failed_indices.append(instrument.name)
            print(f"{instrument.name}: download failed: {exc}")

    if failed_indices:
        print(f"\nFailed indices: {', '.join(failed_indices)}")
        return 1

    print("\nDownload run complete.")
    return 0
