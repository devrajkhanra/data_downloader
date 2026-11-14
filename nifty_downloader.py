import requests
from datetime import datetime, timedelta
import csv
import sys
import os

def get_month_ranges(start_date, end_date):
    """Generate list of (from_date, to_date) tuples for each month."""
    ranges = []
    current = start_date
    while current <= end_date:
        next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = min(next_month - timedelta(days=1), end_date)
        ranges.append((current.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))
        current = month_end + timedelta(days=1)
    return ranges

def download_nifty_data(access_token, start_date_str, instrument_key, interval_minutes=5):
    """Download Nifty data from start_date to today."""
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    except ValueError:
        print("Invalid date format. Use YYYY-MM-DD")
        return []

    end_date = datetime.now()
    if start_date > end_date:
        print("Start date cannot be in the future.")
        return []

    base_url = "https://api.upstox.com/v3"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    all_candles = []

    month_ranges = get_month_ranges(start_date, end_date)

    for from_date, to_date in month_ranges:
        url = f"{base_url}/historical-candle/{instrument_key}/minutes/{interval_minutes}/{to_date}/{from_date}"
        print(f"Fetching data from {from_date} to {to_date}...")

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                candles = data["data"]["candles"]
                all_candles.extend(candles)
                print(f"  Got {len(candles)} candles")
            else:
                print(f"  API error: {data.get('message', 'Unknown error')}")

        except requests.exceptions.RequestException as e:
            print(f"  Request failed: {e}")
            continue

    # Sort candles by timestamp
    all_candles.sort(key=lambda x: x[0])

    print(f"Total candles collected: {len(all_candles)}")
    return all_candles

def get_last_date_from_csv(filename):
    """Get the last date from the CSV file."""
    if not os.path.exists(filename):
        return None
    try:
        with open(filename, 'r', newline='') as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            if not headers:
                return None
            last_row = None
            for row in reader:
                last_row = row
            if last_row and len(last_row) > 0:
                timestamp_str = last_row[0]
                date_part = timestamp_str.split('T')[0]
                return date_part
    except Exception as e:
        print(f"Error reading {filename}: {e}")
    return None

def save_to_csv(candles, filename="nifty50_data.csv", append=False):
    """Save candles to CSV."""
    try:
        if append and os.path.exists(filename):
            rows_by_timestamp = {}
            with open(filename, 'r', newline='') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if row:
                        rows_by_timestamp[row[0]] = row
            for candle in candles:
                rows_by_timestamp[candle[0]] = candle
            candles = [rows_by_timestamp[timestamp] for timestamp in sorted(rows_by_timestamp)]

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Open", "High", "Low", "Close", "Volume", "OpenInterest"])
            for candle in candles:
                writer.writerow(candle)
        print(f"Data saved to {filename}")
    except Exception as e:
        print(f"Error saving file: {e}")

def main():
    print("Nifty Data Downloader")
    print("====================")

    data_type = input("Select data type (spot/future): ").strip().lower()
    if data_type == "spot":
        instrument_key = "NSE_INDEX%7CNifty%2050"
        data_name = "Nifty 50 Spot"
        filename = "nifty50_data.csv"
    elif data_type == "future":
        instrument_key = "NSE_FO%7CNIFTY26MAY"  # May 2026 future
        data_name = "Nifty Future (May 2026)"
        filename = f"{data_type}_data.csv"
    else:
        print("Invalid choice. Please enter 'spot' or 'future'.")
        sys.exit(1)

    filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

    access_token = input("Enter your Upstox access token: ").strip()
    if not access_token:
        print("Access token is required.")
        sys.exit(1)

    append_mode = False
    start_date = None
    last_date = get_last_date_from_csv(filename)

    if last_date:
        next_date = (datetime.strptime(last_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        start_date = next_date
        append_mode = True
        print(f"Found data through {last_date}; resuming from {next_date}.")

    if not start_date:
        start_date = input("Enter start date (YYYY-MM-DD) or start year (YYYY): ").strip()
        if not start_date:
            print("Start date or year is required.")
            sys.exit(1)
        if len(start_date) == 4 and start_date.isdigit():
            start_date = f"{start_date}-01-01"
        append_mode = bool(last_date)

    print(f"\nDownloading {data_name} 5-minute data from {start_date} to today...")
    candles = download_nifty_data(access_token, start_date, instrument_key)

    if candles:
        save_to_csv(candles, filename, append=append_mode)
        print("Download complete!")
    else:
        print("No data downloaded.")

if __name__ == "__main__":
    main()