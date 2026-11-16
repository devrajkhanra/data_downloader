from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias


class InstrumentCategory(str, Enum):
    BROAD = "broad_indices"
    SECTORAL = "sectoral_indices"
    STOCKS = "stocks"


Candle: TypeAlias = list[str | int | float | None]


@dataclass(frozen=True)
class MarketInstrument:
    name: str
    instrument_key: str
    category: InstrumentCategory
    slug: str
    tradingsymbol: str | None = None
    sector_slug: str | None = None
    legacy_slugs: tuple[str, ...] = ()


IndexCategory = InstrumentCategory
IndexInstrument = MarketInstrument
