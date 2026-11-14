from calendar import monthrange
from datetime import date, timedelta


def month_ranges(start_date: date, end_date: date) -> list[tuple[date, date]]:
    """Split an inclusive date range into calendar-month API requests."""
    ranges: list[tuple[date, date]] = []
    current = start_date

    while current <= end_date:
        month_end = date(
            current.year,
            current.month,
            monthrange(current.year, current.month)[1],
        )
        chunk_end = min(month_end, end_date)
        ranges.append((current, chunk_end))
        current = chunk_end + timedelta(days=1)

    return ranges


def parse_iso_date(value: str) -> date:
    """Parse a strictly formatted YYYY-MM-DD date."""
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Date must use YYYY-MM-DD format.")
    return parsed
